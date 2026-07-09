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

import markdown2
import requests

from src.config import Config
from src.formatters import chunk_markdown_preserving_blocks


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
        # HTML 转换会增加约 30%-200% 体积，且 JSON payload 本身有开销；
        # 按 25% 预留足够余量，避免 PushPlus 报服务端验证错误。
        self._markdown_budget = max(1000, int(self._pushplus_max_bytes * 0.25))
        
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
            "content": "消息内容（HTML 格式）",
            "template": "html"
        }

        PushPlus 特点：
        - 国内推送服务，免费额度充足
        - 支持微信公众号推送
        - 支持 HTML 消息格式

        Args:
            content: 消息内容（Markdown 格式，内部会转成手机友好的 HTML）
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
    def _markdown_to_mobile_html(markdown_text: str) -> str:
        """
        把 Markdown 报告转成适合手机微信阅读的 HTML。

        使用 inline style，因为部分客户端会过滤 <style> 块。
        """
        html_content = markdown2.markdown(
            markdown_text,
            extras=["tables", "fenced-code-blocks", "break-on-newline", "cuddled-lists"],
        )

        # 包裹容器，设置基础字体和行距
        container_style = (
            "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
            "font-size:14px;line-height:1.6;color:#333;"
        )

        def style_tag(tag: str, style: str) -> None:
            nonlocal html_content
            pattern = re.compile(rf'<{tag}\b([^>]*?)(/?)>')
            def repl(match):
                attrs = match.group(1) or ""
                slash = match.group(2) or ""
                if 'style=' in attrs:
                    return match.group(0)
                return f'<{tag}{attrs} style="{style}"{slash}>'
            html_content = pattern.sub(repl, html_content)

        style_tag("h1", "font-size:18px;line-height:1.4;color:#1a1a1a;margin:16px 0 8px 0;border-bottom:1px solid #e0e0e0;padding-bottom:4px;")
        style_tag("h2", "font-size:16px;line-height:1.4;color:#2c3e50;margin:14px 0 6px 0;")
        style_tag("h3", "font-size:15px;line-height:1.4;color:#34495e;margin:12px 0 5px 0;")
        style_tag("p", "margin:6px 0;line-height:1.6;font-size:14px;color:#333;")
        style_tag("strong", "color:#2c3e50;")
        style_tag("table", "width:100%;border-collapse:collapse;margin:8px 0;font-size:13px;")
        style_tag("tr", "border-bottom:1px solid #eee;")
        style_tag("th", "background:#f5f7fa;padding:6px 4px;text-align:left;font-weight:600;border:1px solid #ddd;")
        style_tag("td", "padding:6px 4px;border:1px solid #eee;vertical-align:top;")
        style_tag("ul", "margin:4px 0;padding-left:16px;")
        style_tag("ol", "margin:4px 0;padding-left:16px;")
        style_tag("li", "margin:3px 0;line-height:1.5;font-size:14px;")
        style_tag("blockquote", "margin:6px 0;padding:6px 10px;background:#f8f9fa;border-left:3px solid #3498db;color:#555;")
        style_tag("code", "padding:2px 4px;font-size:85%;background:rgba(27,31,35,0.05);border-radius:3px;font-family:SFMono-Regular,Consolas,monospace;")
        style_tag("pre", "padding:10px;overflow:auto;line-height:1.45;background:#f6f8fa;border-radius:3px;font-size:12px;")
        style_tag("hr", "height:1px;padding:0;margin:12px 0;background:#e1e4e8;border:0;")

        return f'<div style="{container_style}">{html_content}</div>'

    def _send_pushplus_message(
        self,
        api_url: str,
        content: str,
        title: str,
        *,
        timeout_seconds: Optional[float] = None,
    ) -> bool:
        html_content = self._markdown_to_mobile_html(content)

        payload = {
            "token": self._pushplus_token,
            "title": title,
            "content": html_content,
            "template": "html",
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
            logger.error(f"PushPlus 返回错误: {error_msg}")
            return False

        logger.error(f"PushPlus 请求失败: HTTP {response.status_code}")
        return False

    def _send_pushplus_chunked(self, api_url: str, content: str, title: str, markdown_budget: int) -> bool:
        """分批发送长 PushPlus 消息，尽量在段落/表格边界处分割。"""
        chunks = chunk_markdown_preserving_blocks(
            content,
            markdown_budget,
            len_fn=lambda s: len(s.encode("utf-8")),
            add_page_marker=True,
        )
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
