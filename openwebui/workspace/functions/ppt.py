"""
title: Powerpoint Generator
description: Generate powerpoint with user's input queue and provide download links
author: changchiyou
author_url: https://github.com/changchiyou
funding_url: https://github.com/open-webui
version: 0.0.1
icon_url: data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0idXRmLTgiPz4KPCEtLSBVcGxvYWRlZCB0bzogU1ZHIFJlcG8sIHd3dy5zdmdyZXBvLmNvbSwgR2VuZXJhdG9yOiBTVkcgUmVwbyBNaXhlciBUb29scyAtLT4KPHN2ZyB3aWR0aD0iODAwcHgiIGhlaWdodD0iODAwcHgiIHZpZXdCb3g9IjAgMCAyNCAyNCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KICA8dGl0bGU+bWljcm9zb2Z0X3Bvd2VycG9pbnQ8L3RpdGxlPgogIDxyZWN0IHdpZHRoPSIyNCIgaGVpZ2h0PSIyNCIgZmlsbD0ibm9uZSIvPgogIDxwYXRoIGQ9Ik0xNCw1VjcuNzhBMywzLDAsMCwxLDE2LDd2M2gzYTMsMywwLDAsMS01LDIuMjJWMTRoNnYxSDE0djFoNnYxSDE0djJoOFY1Wm0zLDRWNmEzLDMsMCwwLDEsMywzWiIvPgogIDxnPgogICAgPHBhdGggZD0iTTIsNC44VjE5LjIxTDE0LDIxVjMuMDhaTTkuNiwxMi42MWEzLjQsMy40LDAsMCwxLTIuNS43MmwtLjg5LDB2My4zNGwtMS40LS4xOFY3Ljg5TDcuMjcsNy42YTMuMTEsMy4xMSwwLDAsMSwyLjQxLjQ3LDIuNzEsMi43MSwwLDAsMSwuOCwyLjE3QTMsMywwLDAsMSw5LjYsMTIuNjFaIi8+CiAgICA8cGF0aCBkPSJNNy4xOCw4Ljg2bC0xLC4wOHYzLjE0SDdhMi40MywyLjQzLDAsMCwwLDEuNTgtLjQxQTEuNjEsMS42MSwwLDAsMCw5LDEwLjM1YTEuNDgsMS40OCwwLDAsMC0uNDUtMS4yQTEuOTQsMS45NCwwLDAsMCw3LjE4LDguODZaIi8+CiAgPC9nPgo8L3N2Zz4=
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import os
from apps.webui.models.files import Files
import uuid
import logging
import time
import textwrap
import requests
import asyncio


# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class FileData(BaseModel):
    id: str
    filename: str
    meta: Dict[str, Any]


class Action:
    class Valves(BaseModel):
        show_status: bool = Field(
            default=True, description="Show status of the action."
        )
        serviceAddress: str = Field(
            default="http://192.168.63.122", description="The address of powerpoint-generater service."
        )
        servicePort: str = Field(
            default="5001", description="The port number of powerpoint-generater service."
        )
        PPT_SECRET_KEY: str = Field(
            default="", description="The secret key for ppt flask app."
        )

    def __init__(self):
        self.valves = self.Valves()
        self.filename = ""

    def create_or_get_file(self, user_id: str, json_data: str) -> str:
        directory = "action_embed"

        logger.debug(f"Attempting to create or get file: {self.filename}.html")

        # Check if the file already exists
        existing_files = Files.get_files()
        for file in existing_files:
            if (
                file.filename == f"{directory}/{user_id}/{self.filename}.html"
                and file.user_id == user_id
            ):
                logger.debug("Existing file found. Updating content.")
                # Update the existing file with new JSON data
                self.update_html_content(file.meta["path"], json_data)
                return file.id

        # If the file doesn''t exist, create it
        base_path = os.path.join("uploads", directory)
        os.makedirs(base_path, exist_ok=True)
        file_path = os.path.join(base_path, f"{self.filename}.html")

        logger.debug(f"Creating new file at: {file_path}")
        self.update_html_content(file_path, json_data)

        file_id = str(uuid.uuid4())
        meta = {
            "source": file_path,
            "title": "Powerpoint Generator",
            "content_type": "text/html",
            "size": os.path.getsize(file_path),
            "path": file_path,
        }

        # Create a new file entry
        file_data = FileData(
            id=file_id, filename=f"{directory}/{user_id}/{self.filename}.html", meta=meta
        )
        new_file = Files.insert_new_file(user_id, file_data)
        logger.debug(f"New file created with ID: {new_file.id}")
        return new_file.id

    def update_html_content(self, file_path: str, html_content: str):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.debug(f"HTML content updated at: {file_path}")

    def format_size(self, size_in_bytes):
        """Convert bytes to a human-readable format (KB, MB, GB, etc.)."""
        if size_in_bytes == 0:
            return "0 Bytes"

        size_units = ["Bytes", "KB", "MB", "GB", "TB"]
        index = 0

        while size_in_bytes >= 1024 and index < len(size_units) - 1:
            size_in_bytes /= 1024.0
            index += 1

        return f"{size_in_bytes:.1f} {size_units[index]}"

    def get_file_size(self, filename):
        try:
            response = requests.get(f"http://ppt:5001/file_size/{filename}")
            response.raise_for_status()  # Raise an error for bad responses

            data = response.json()
            size_in_bytes = data.get("size_in_bytes")

            # Format the size
            formatted_size = self.format_size(size_in_bytes)

            return formatted_size

        except requests.exceptions.RequestException as e:
            logger.debug(f"Error retrieving file size: {e}")


    async def action(
        self,
        body: dict,
        __user__=None,
        __event_emitter__=None,
        __event_call__=None,
    ) -> Optional[dict]:
        logger.debug(f"action:{__name__} started")

        if __event_emitter__ and __event_call__ and __user__:
            presentation_title = await __event_call__(
                {
                    "type": "input",
                    "data": {
                        "title": "Write down your presentation title",
                        "message": "The title would be placed at the first page of powerpoint",
                        "placeholder": "Enter your title here",
                    },
                }
            )
            await asyncio.sleep(1)

            await __event_emitter__(
                {
                    "type": "status",
                    "data": {
                        "description": "Generating Powerpoint",
                        "done": False,
                    },
                }
            )
            await asyncio.sleep(1)

            try:
                user_id = __user__["id"]
                user_name = __user__["name"]

                self.filename = f"{presentation_title.replace(' ', '_')}-{str(int(time.time() * 1000))}"

                data = {
                    'number_of_slide': -1,
                    'user_text': body["messages"][-1]["content"],
                    'presentation_title': presentation_title,
                    'presenter_name': user_name,
                    'filename': self.filename,
                }
                requests.post(
                    f"http://ppt:{self.valves.servicePort}/generator",
                    data=data,
                    headers={"Authorization": f"Bearer {self.valves.PPT_SECRET_KEY}"},
                )

                html_content = textwrap.dedent(f"""
                <!DOCTYPE html>
                    <html lang="en">
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>Download File</title>
                        <style>
                            body {{
                                font-family: Arial, sans-serif;
                                display: flex;
                                justify-content: center;
                                align-items: center;
                                height: 100vh;
                                margin: 0;
                                background-color: #f0f0f0;
                            }}
                            .download-button {{
                                display: flex;
                                align-items: center;
                                background-color: #2c2c2c;
                                color: #ffffff;
                                padding: 10px 15px;
                                border-radius: 5px;
                                cursor: pointer;
                                transition: background-color 0.3s;
                            }}
                            .download-button:hover {{
                                background-color: #3a3a3a;
                            }}
                            .icon {{
                                width: 20px;
                                height: 20px;
                                margin-right: 10px;
                                background-color: #ffffff;
                                mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z'/%3E%3C/svg%3E") no-repeat center / contain;
                                -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z'/%3E%3C/svg%3E") no-repeat center / contain;
                            }}
                            .file-info {{
                                display: flex;
                                flex-direction: column;
                            }}
                            .file-name {{
                                font-weight: bold;
                            }}
                            .file-meta {{
                                font-size: 0.8em;
                                opacity: 0.7;
                            }}
                        </style>
                    </head>
                    <body>
                        <div class="download-button" onclick="downloadFile()">
                            <div class="icon"></div>
                            <div class="file-info">
                                <span class="file-name">{self.filename}.pptx</span>
                                <span class="file-meta">File {self.get_file_size(self.filename+'.pptx')}</span>
                            </div>
                        </div>

                        <script>
                            function downloadFile() {{
                                const filename = '{self.filename}.pptx';
                                const serviceAddress = '{self.valves.serviceAddress}';
                                const servicePort = '{self.valves.servicePort}';
                                const downloadUrl = `${{serviceAddress}}:${{servicePort}}/download/${{filename}}`;
                                
                                fetch(downloadUrl)
                                    .then(response => {{
                                        if (response.ok) {{
                                            return response.blob();
                                        }}
                                        throw new Error('Network response was not ok.');
                                    }})
                                    .then(blob => {{
                                        const url = window.URL.createObjectURL(blob);
                                        const a = document.createElement('a');
                                        a.style.display = 'none';
                                        a.href = url;
                                        a.download = filename;
                                        document.body.appendChild(a);
                                        a.click();
                                        window.URL.revokeObjectURL(url);
                                    }})
                                    .catch(error => {{
                                        console.error('There was a problem with the download:', error);
                                        alert('下載過程中發生了意外狀況，可能因為定期清除流程導致檔案已被刪除、可嘗試重新產生一份 PowerPoint 並重新點擊下載連結。若多次嘗試後還是沒能成功下載，請聯絡開發人員。');
                                    }});
                            }}
                        </script>
                    </body>
                    </html>
                """)

                file_id = self.create_or_get_file(user_id, html_content)

                # Create the HTML embed tag
                html_embed_tag = f"{{{{HTML_FILE_ID_{file_id}}}}}"

                # Append the HTML embed tag to the original content on a new line
                original_content = body["messages"][-1]["content"]
                body["messages"][-1][
                    "content"
                ] = f"{original_content}\n\n{html_embed_tag}"

                await __event_emitter__(
                    {
                        "type": "status",
                        "data": {
                            "description": "Powerpoint generated",
                            "done": True,
                        },
                    }
                )

                logger.debug("Action done successfully.")

            except Exception as e:
                error_message = f"Error generating powerpoint: {str(e)}"
                logger.error(f"Error: {error_message}")

                if self.valves.show_status:
                    await __event_emitter__(
                        {
                            "type": "status",
                            "data": {
                                "description": "⚠️ Error Generating Powerpoint",
                                "done": True,
                            },
                        }
                    )
        else:
            logger.error(f"__user__: {__user__}")
            logger.error(f"__event_emitter__: {__event_emitter__}")
            logger.error(f"__event_call__: {__event_call__}")

        logger.debug(f"action:{__name__} completed")
        return body