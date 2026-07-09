# -*- coding: utf-8 -*-
"""
PushPlus 发送提醒服务

职责：
1. 通过 PushPlus API 发送 PushPlus 消息
"""
import logging
import re
import time
from typing import Optional
from datetime import datetime

import requests

from src.config import Config
from src.formatters import chunk_content_by_max_bytes, markdown_tables_to_key_value_rows


logger = logging.getLogger(__name__)


class PushplusSender:
    
    def __init__(self, config: Config):
        """
        初始化 PushPlus 配置

        Args:
            config: 配置对象
        """
        self._pushplus_token = getattr(config, 'pushplus_token', None)
        self._pushplus_topic = getattr(config, 'pushplus_topic', None)
        self._pushplus_max_bytes = getattr(config, 'pushplus_max_bytes', 20000)
        # PushPlus 单条内容上限约 20000 字节；
        # 预留 JSON payload 开销，Markdown 格式无 HTML 膨胀。
        self._markdown_budget = max(1000, self._pushplus_max_bytes - 2000)
        
    def send_to_pushplus(
        self,
        content: str,
        title: Optional[str] = None,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        """
        推送消息到 PushPlus

        PushPlus API 格式：
        POST https://www.pushplus.plus/send
        {
            "token": "用户令牌",
            "title": "消息标题",
            "content": "消息内容（Markdown 格式）",
            "template": "markdown"
        }

        PushPlus 特点：
        - 国内推送服务，免费额度充足
        - 支持微信公众号推送
        - 支持 Markdown 消息格式

        Args:
            content: 消息内容（Markdown 格式；内部会把表格转为手机友好的键值行）
            title: 消息标题（可选）

        Returns:
            是否发送成功
        """
        if not self._pushplus_token:
            logger.warning("PushPlus Token 未配置，跳过推送")
            return False

        api_url = "https://www.pushplus.plus/send"

        if title is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
            title = f"📈 股票分析报告 - {date_str}"

        try:
            content_bytes = len(content.encode('utf-8'))
            if content_bytes > self._markdown_budget:
                logger.info(
                    "PushPlus 消息内容超长(%s字节/%s字符)，将分批发送",
                    content_bytes,
                    len(content),
                )
                return self._send_pushplus_chunked(
                    api_url,
                    content,
                    title,
                    self._markdown_budget,
                )

            return self._send_pushplus_message(api_url, content, title, timeout_seconds=timeout_seconds)
        except Exception as e:
            logger.error(f"发送 PushPlus 消息失败: {e}")
            return False

    @staticmethod
    def _format_pushplus_content(markdown_text: str) -> str:
        """
        把 Markdown 报告整理成更适合手机微信阅读的 Markdown。

        核心优化：把表格转成键值行，避免微信里表格排版错乱。
        """
        # 将表格转为键值列表，保持其他 Markdown 结构不变
        text = markdown_tables_to_key_value_rows(markdown_text, bullet="•")

        # 清理连续空行，让段落间距更紧凑
        text = re.sub(r"\n{3,}", "\n\n", text)

        # 在长表格转列表后，部分键值对较长；为提升可读性，
        # 在二级标题前加一行分隔（markdown 已有 ##，这里无需额外处理）
        return text.strip()

    def _send_pushplus_message(
        self,
        api_url: str,
        content: str,
        title: str,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        formatted_content = self._format_pushplus_content(content)

        payload = {
            "token": self._pushplus_token,
            "title": title,
            "content": formatted_content,
            "template": "markdown",
        }

        if self._pushplus_topic:
            payload["topic"] = self._pushplus_topic

        response = requests.post(api_url, json=payload, timeout=timeout_seconds or 10)

        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 200:
                logger.info("PushPlus 消息发送成功")
                return True

            error_msg = result.get('msg', '未知错误')
            error_data = result.get('data')
            logger.error(f"PushPlus 返回错误: {error_msg}, data={error_data}")
            return False

        logger.error(f"PushPlus 请求失败: HTTP {response.status_code}")
        return False

    def _send_pushplus_chunked(self, api_url: str, content: str, title: str, markdown_budget: int) -> bool:
        """分批发送长 PushPlus 消息，给 JSON payload 预留空间。"""
        chunks = chunk_content_by_max_bytes(content, markdown_budget, add_page_marker=True)
        total_chunks = len(chunks)
        success_count = 0

        logger.info(f"PushPlus 分批发送：共 {total_chunks} 批")

        for i, chunk in enumerate(chunks):
            chunk_title = f"{title} ({i+1}/{total_chunks})" if total_chunks > 1 else title
            if self._send_pushplus_message(api_url, chunk, chunk_title):
                success_count += 1
                logger.info(f"PushPlus 第 {i+1}/{total_chunks} 批发送成功")
            else:
                logger.error(f"PushPlus 第 {i+1}/{total_chunks} 批发送失败")

            if i < total_chunks - 1:
                time.sleep(1)

        return success_count == total_chunks
