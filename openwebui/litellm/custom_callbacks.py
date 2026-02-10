from litellm.integrations.custom_logger import CustomLogger
import litellm
from litellm.proxy.proxy_server import UserAPIKeyAuth, DualCache
from typing import Optional, Literal
from litellm._logging import verbose_proxy_logger

# This file includes the custom callbacks for LiteLLM Proxy
# Once defined, these can be passed in proxy_config.yaml
class MyCustomHandler(CustomLogger): # https://docs.litellm.ai/docs/observability/custom_callback#callback-class
    # Class variables or attributes
    def __init__(self):
        self.debug = True
        pass

    def _deduplicate_tool_results(self, messages: list) -> tuple[list, int]:
        """Remove duplicate tool_result blocks with same tool_use_id across ALL messages"""
        if not messages:
            return messages, 0

        cleaned_messages = []
        duplicates_removed = 0
        # Global tool_result_map to track tool_use_ids across ALL messages
        global_tool_result_map = {}

        for msg in messages:
            if not isinstance(msg.get('content'), list):
                cleaned_messages.append(msg)
                continue

            has_tool_results = any(
                isinstance(block, dict) and block.get('type') == 'tool_result'
                for block in msg.get('content', [])
            )

            if not has_tool_results:
                cleaned_messages.append(msg)
                continue

            cleaned_content = []

            for block in msg['content']:
                if not isinstance(block, dict):
                    cleaned_content.append(block)
                    continue

                if block.get('type') == 'tool_result':
                    tool_use_id = block.get('tool_use_id')

                    if not tool_use_id:
                        cleaned_content.append(block)
                        continue

                    if tool_use_id in global_tool_result_map:
                        # This is a duplicate - skip it entirely
                        duplicates_removed += 1

                        if self.debug:
                            verbose_proxy_logger.warning(f"[ToolResultDedup] ⚠️  Found duplicate tool_result: {tool_use_id}")
                            verbose_proxy_logger.warning(f"[ToolResultDedup] 🚫 Skipping duplicate (already exists in previous message)")
                        continue
                    else:
                        # First time seeing this tool_use_id across all messages
                        global_tool_result_map[tool_use_id] = block
                        cleaned_content.append(block)

                        if self.debug:
                            verbose_proxy_logger.debug(f"[ToolResultDedup] ✓ Added tool_result: {tool_use_id}")
                else:
                    cleaned_content.append(block)

            if cleaned_content:
                msg_copy = msg.copy()
                msg_copy['content'] = cleaned_content
                cleaned_messages.append(msg_copy)

        return cleaned_messages, duplicates_removed

    #### CALL HOOKS - proxy only ####

    async def async_pre_call_hook(self, user_api_key_dict: UserAPIKeyAuth, cache: DualCache, data: dict, call_type: Literal[
            "completion",
            "text_completion",
            "embeddings",
            "image_generation",
            "moderation",
            "audio_transcription",
        ]):
        tags_set = set(data["metadata"].get("tags", []))
        tags_set.add(data["proxy_server_request"]["headers"]["host"])
        data["metadata"]["tags"] = list(tags_set)

        # Deduplicate tool_result blocks to prevent API 400 errors
        if "messages" in data:
            original_count = len(data["messages"])
            cleaned_messages, duplicates_removed = self._deduplicate_tool_results(data["messages"])
            data["messages"] = cleaned_messages

            if self.debug and duplicates_removed > 0:
                verbose_proxy_logger.warning(f"[ToolResultDedup] Messages: {original_count} → {len(cleaned_messages)}")
                verbose_proxy_logger.warning(f"[ToolResultDedup] 🚫 Removed {duplicates_removed} duplicate tool_result(s)")

        return data 

    async def async_post_call_failure_hook(
        self, 
        request_data: dict,
        original_exception: Exception, 
        user_api_key_dict: UserAPIKeyAuth
    ):
        pass

    async def async_post_call_success_hook(
        self,
        data: dict,
        user_api_key_dict: UserAPIKeyAuth,
        response,
    ):
        pass

    async def async_moderation_hook( # call made in parallel to llm api call
        self,
        data: dict,
        user_api_key_dict: UserAPIKeyAuth,
        call_type: Literal["completion", "embeddings", "image_generation", "moderation", "audio_transcription"],
    ):
        pass

    async def async_post_call_streaming_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        response: str,
    ):
        pass
proxy_handler_instance = MyCustomHandler()