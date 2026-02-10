from litellm.integrations.custom_logger import CustomLogger
import litellm
from litellm.proxy.proxy_server import UserAPIKeyAuth, DualCache
from typing import Optional, Literal, Dict
from litellm._logging import verbose_proxy_logger
import os
import re

# This file includes the custom callbacks for LiteLLM Proxy
# Once defined, these can be passed in proxy_config.yaml
class MyCustomHandler(CustomLogger): # https://docs.litellm.ai/docs/observability/custom_callback#callback-class
    # Class variables or attributes
    def __init__(self):
        self.debug = True
        self.custom_pricing_enabled = os.getenv("ENABLE_CUSTOM_PRICING", "true").lower() == "true"
        self.price_multiplier = float(os.getenv("PRICE_MULTIPLIER", "1.0"))

        # Mapping cache: TrendMicro model name -> LiteLLM price table key
        self.model_mapping_cache = {}

        # Fallback pricing for models not found in price table
        self.fallback_pricing = self._load_fallback_pricing()

        if self.custom_pricing_enabled:
            verbose_proxy_logger.info(
                f"[CustomPricing] 🚀 Custom pricing enabled | Multiplier: {self.price_multiplier}x"
            )
        pass

    def _load_fallback_pricing(self) -> Dict[str, Dict[str, float]]:
        """
        Load fallback pricing for models not found in LiteLLM price table

        Priority:
        1. From environment variables (CUSTOM_PRICING_<MODEL_NAME>)
        2. From hardcoded defaults for known models
        3. Generic fallback for unknown models
        """
        fallback = {}

        # Check environment variables for custom pricing
        # Format: CUSTOM_PRICING_CYBERTRON_0906="input:0.000001,output:0.000003"
        for key, value in os.environ.items():
            if key.startswith("CUSTOM_PRICING_"):
                model_name = key.replace("CUSTOM_PRICING_", "").lower().replace("_", "-")
                try:
                    parts = value.split(",")
                    input_cost = float(parts[0].split(":")[1])
                    output_cost = float(parts[1].split(":")[1])
                    fallback[model_name] = {
                        "input_cost_per_token": input_cost,
                        "output_cost_per_token": output_cost,
                    }
                    verbose_proxy_logger.info(
                        f"[CustomPricing] Loaded custom pricing from env for {model_name}"
                    )
                except Exception as e:
                    verbose_proxy_logger.warning(
                        f"[CustomPricing] Failed to parse custom pricing for {key}: {e}"
                    )

        # Hardcoded fallback for known models without price table entries
        hardcoded = {
            # Nvidia Nemotron models (estimate based on similar 30B models)
            "nvidia-nemotron-3-nano-30b-gmi": {
                "input_cost_per_token": 0.0000003,   # Similar to Llama 30B
                "output_cost_per_token": 0.0000006,
            },
            "nvidia-nemotron-nano-3-30b-aws": {
                "input_cost_per_token": 0.0000003,
                "output_cost_per_token": 0.0000006,
            },
            # Stable Diffusion 3.5 Large (estimate based on SD 3.0)
            "stable-diffusion-3.5-large": {
                "input_cost_per_token": 0.000004,
                "output_cost_per_token": 0.000012,
            },
            # Unknown models - conservative pricing
            "cybertron-0906": {
                "input_cost_per_token": 0.000002,
                "output_cost_per_token": 0.000008,
            },
            "gpt-c35s": {
                "input_cost_per_token": 0.0000005,  # Similar to GPT-3.5
                "output_cost_per_token": 0.000002,
            },
            "primus-christmas": {
                "input_cost_per_token": 0.000002,
                "output_cost_per_token": 0.000008,
            },
            "primus-labor-70b": {
                "input_cost_per_token": 0.000001,   # 70B model
                "output_cost_per_token": 0.000003,
            },
            # Special deployment versions - map to base model pricing
            "qwen3-vl-4b-it-gmi-ray": {
                "input_cost_per_token": 0.0000001,  # Small model
                "output_cost_per_token": 0.0000003,
            },
            "smollm3-3b-gmi-ray": {
                "input_cost_per_token": 0.0000001,  # Small model
                "output_cost_per_token": 0.0000003,
            },
        }

        # Merge: env vars override hardcoded values
        hardcoded.update(fallback)

        return hardcoded

    def _normalize_model_name(self, model_name: str) -> str:
        """
        Normalize model name for comparison
        Examples:
          - "claude-3.5-sonnet" -> "claude35sonnet"
          - "claude-3-5-sonnet" -> "claude35sonnet"
          - "gpt-4o" -> "gpt4o"
        """
        normalized = model_name.lower()
        normalized = re.sub(r'[-_\.]', '', normalized)
        return normalized

    def _find_price_table_key(self, model: str) -> Optional[str]:
        """
        Find the best matching key in litellm.model_cost for the given model

        Matching strategies (in order):
        1. Exact match
        2. Prefix match (with provider name)
        3. Normalized exact match
        4. Component-based fuzzy match
        5. Version-aware match (find latest version)

        Returns:
            matched_key or None
        """
        # Check cache first
        if model in self.model_mapping_cache:
            return self.model_mapping_cache[model]

        price_table = litellm.model_cost

        # Strategy 1: Exact match
        if model in price_table:
            self.model_mapping_cache[model] = model
            if self.debug:
                verbose_proxy_logger.debug(f"[CustomPricing] ✓ Exact match: {model}")
            return model

        # Strategy 2: Try common provider prefixes
        common_prefixes = [
            'openai/', 'anthropic/', 'gemini/', 'vertex_ai/', 'vertex_ai_beta/',
            'bedrock/', 'azure/', 'azure_ai/', 'cohere/', 'replicate/',
            'replicate/anthropic/', 'deepinfra/', 'deepinfra/anthropic/',
            'heroku/', 'vercel_ai_gateway/', 'vercel_ai_gateway/anthropic/',
            'groq/', 'together_ai/', 'perplexity/', 'mistral/', 'fireworks_ai/',
            'anyscale/', 'databricks/', 'github_copilot/', 'openrouter/',
            'xai/', 'cerebras/', 'nscale/', 'gmi/',
        ]

        for prefix in common_prefixes:
            candidate = f"{prefix}{model}"
            if candidate in price_table:
                self.model_mapping_cache[model] = candidate
                if self.debug:
                    verbose_proxy_logger.debug(f"[CustomPricing] ✓ Prefix match: {model} -> {candidate}")
                return candidate

        # Strategy 3: Normalized exact match
        normalized_input = self._normalize_model_name(model)
        for key in price_table.keys():
            normalized_key = self._normalize_model_name(key)
            if normalized_input == normalized_key:
                self.model_mapping_cache[model] = key
                if self.debug:
                    verbose_proxy_logger.debug(f"[CustomPricing] ✓ Normalized match: {model} -> {key}")
                return key

        # Strategy 4: Component-based fuzzy match
        # Break model into components (e.g., "claude-4.5-sonnet" -> ["claude", "4", "5", "sonnet"])
        model_components = re.findall(r'[a-z]+|\d+\.?\d*', model.lower())

        best_match = None
        best_ratio = 0

        for key in price_table.keys():
            key_components = re.findall(r'[a-z]+|\d+\.?\d*', key.lower())

            # Count matching components
            matches = sum(1 for comp in model_components if comp in key_components)
            match_ratio = matches / len(model_components) if model_components else 0

            if match_ratio > best_ratio and match_ratio >= 0.7:  # 70% component match threshold
                best_ratio = match_ratio
                # Extract date if exists for version sorting
                date_match = re.search(r'(\d{8})', key)
                date_val = int(date_match.group(1)) if date_match else 0
                best_match = (key, date_val, match_ratio)

        if best_match and best_ratio >= 0.7:
            matched_key = best_match[0]
            self.model_mapping_cache[model] = matched_key
            if self.debug:
                verbose_proxy_logger.debug(
                    f"[CustomPricing] ≈ Component match: {model} -> {matched_key} ({best_ratio*100:.0f}%)"
                )
            return matched_key

        # Strategy 5: Partial string match with high similarity
        best_similarity = 0
        best_match_key = None

        for key in price_table.keys():
            # Check if model name is substring of key or vice versa
            if model.lower() in key.lower() or key.lower() in model.lower():
                similarity = min(len(model), len(key)) / max(len(model), len(key))
                if similarity > best_similarity and similarity >= 0.6:
                    best_similarity = similarity
                    best_match_key = key

        if best_match_key:
            self.model_mapping_cache[model] = best_match_key
            if self.debug:
                verbose_proxy_logger.debug(
                    f"[CustomPricing] ≈ Similarity match: {model} -> {best_match_key} ({best_similarity*100:.0f}%)"
                )
            return best_match_key

        # No match found
        if self.debug:
            verbose_proxy_logger.debug(f"[CustomPricing] ✗ No price table match for: {model}")
        return None

    def _get_custom_pricing(self, model: str) -> Optional[Dict[str, float]]:
        """
        Get custom pricing for a model

        Priority:
        1. From litellm.model_cost (updated by LiteLLM's scheduled reload)
        2. From fallback_pricing (hardcoded or env vars)
        3. Generic fallback

        Returns:
            Dict with 'input_cost_per_token' and 'output_cost_per_token'
        """
        # Priority 1: Try to find in litellm.model_cost via mapping
        price_key = self._find_price_table_key(model)
        if price_key:
            price_info = litellm.model_cost.get(price_key)
            if price_info:
                # Extract relevant pricing fields
                pricing = {
                    "input_cost_per_token": price_info.get("input_cost_per_token", 0),
                    "output_cost_per_token": price_info.get("output_cost_per_token", 0),
                }

                # Apply multiplier if configured
                if self.price_multiplier != 1.0:
                    pricing = self._apply_multiplier(pricing)

                return pricing

        # Priority 2: Try fallback pricing
        if model in self.fallback_pricing:
            pricing = self.fallback_pricing[model].copy()

            if self.debug:
                verbose_proxy_logger.info(
                    f"[CustomPricing] 💡 Using fallback pricing for: {model}"
                )

            # Apply multiplier
            if self.price_multiplier != 1.0:
                pricing = self._apply_multiplier(pricing)

            return pricing

        # Priority 3: Generic fallback
        verbose_proxy_logger.warning(
            f"[CustomPricing] ⚠️  Using generic fallback pricing for: {model}"
        )

        generic_pricing = {
            "input_cost_per_token": 0.000001,   # $0.001 per 1K tokens
            "output_cost_per_token": 0.000003,  # $0.003 per 1K tokens
        }

        if self.price_multiplier != 1.0:
            generic_pricing = self._apply_multiplier(generic_pricing)

        return generic_pricing

    def _apply_multiplier(self, pricing: Dict[str, float]) -> Dict[str, float]:
        """Apply price multiplier to pricing information"""
        result = {}

        cost_fields = [
            'input_cost_per_token',
            'output_cost_per_token',
            'input_cost_per_character',
            'output_cost_per_character',
            'input_cost_per_image',
            'output_cost_per_image',
            'input_cost_per_audio_token',
            'output_cost_per_audio_token',
            'output_cost_per_reasoning_token',
            'cache_creation_input_token_cost',
            'cache_read_input_token_cost',
        ]

        for field in cost_fields:
            if field in pricing and pricing[field] is not None:
                result[field] = float(pricing[field]) * self.price_multiplier
            elif field in pricing:
                result[field] = pricing[field]

        return result

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

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        """
        Override success event to calculate and log custom pricing

        This hook is called AFTER the API call succeeds.
        We read from litellm.model_cost which has been automatically updated
        by LiteLLM's scheduled reload mechanism (configured via Admin UI).
        """
        try:
            if not self.custom_pricing_enabled:
                return

            model = kwargs.get("model")
            if not model:
                return

            # Get custom pricing (from litellm.model_cost or fallback)
            pricing_info = self._get_custom_pricing(model)
            if not pricing_info:
                return

            # Calculate custom cost
            usage = response_obj.get("usage", {})
            if not usage:
                return

            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

            input_cost_per_token = pricing_info.get("input_cost_per_token", 0)
            output_cost_per_token = pricing_info.get("output_cost_per_token", 0)

            input_cost = prompt_tokens * input_cost_per_token
            output_cost = completion_tokens * output_cost_per_token
            total_cost = input_cost + output_cost

            if self.debug:
                verbose_proxy_logger.info(
                    f"[CustomPricing] 💰 {model} | "
                    f"Tokens: {prompt_tokens}in + {completion_tokens}out = {prompt_tokens + completion_tokens} | "
                    f"Cost: ${total_cost:.6f} (${input_cost:.6f} + ${output_cost:.6f}) | "
                    f"Multiplier: {self.price_multiplier}x"
                )

            # Store custom cost in metadata for logging/tracking
            litellm_params = kwargs.get("litellm_params", {})
            metadata = litellm_params.get("metadata", {})
            metadata["custom_cost"] = total_cost
            metadata["custom_input_cost"] = input_cost
            metadata["custom_output_cost"] = output_cost
            metadata["price_multiplier"] = self.price_multiplier

        except Exception as e:
            verbose_proxy_logger.error(f"[CustomPricing] ❌ Error calculating cost: {str(e)}")
            import traceback
            verbose_proxy_logger.debug(f"[CustomPricing] Traceback: {traceback.format_exc()}")

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
