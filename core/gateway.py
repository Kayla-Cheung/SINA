import os
import asyncio
import json
from typing import Optional, Any, Type, Dict
from pydantic import BaseModel, ValidationError
from openai import AsyncOpenAI
from dotenv import load_dotenv

# 自动寻找项目根目录的 .env 文件
load_dotenv()

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "••••"
    return "••••" + value[-4:]


def looks_masked(value: Optional[str]) -> bool:
    if not value:
        return True
    stripped = value.strip()
    return stripped.startswith("•") or stripped.startswith("***")


class AsyncLLMGateway:
    """
    SINA V3 统一大模型网关
    负责：并发控制、指数退避重试、JSON 强制校验、错误降级
    """
    def __init__(self, max_concurrency: int = 5, api_key: Optional[str] = None):
        key = api_key or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY") or "sk-placeholder"
        self.api_key = key
        self.base_url = os.getenv("LLM_BASE_URL") or DEFAULT_BASE_URL
        self.model = os.getenv("LLM_MODEL") or DEFAULT_MODEL
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )
        self.semaphore = asyncio.Semaphore(int(os.getenv("MAX_LLM_CONCURRENCY", str(max_concurrency))))
        self.last_system_prompt = ""
        self.last_user_prompt = ""
        self.last_raw_response = ""
        self.agent_prompts: Dict[str, Dict[str, Any]] = {}
        self.embedding_base_url = ""
        self.embedding_api_key = ""
        self.embedding_model = "gemini-embedding-2"
        self.embedding_provider = "google"
        self.thinking_enabled = False

    def reconfigure(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        embedding_base_url: Optional[str] = None,
        embedding_api_key: Optional[str] = None,
        embedding_model: Optional[str] = None,
        embedding_provider: Optional[str] = None,
        thinking_enabled: Optional[bool] = None,
    ) -> None:
        """Mutate this singleton in place so existing `import gateway` bindings stay valid."""
        if api_key and not looks_masked(api_key):
            self.api_key = api_key
        if base_url:
            self.base_url = base_url.rstrip("/")
        if model:
            self.model = model
        if embedding_base_url is not None:
            self.embedding_base_url = embedding_base_url
        if embedding_api_key is not None and not looks_masked(embedding_api_key):
            self.embedding_api_key = embedding_api_key
        if embedding_model is not None:
            self.embedding_model = embedding_model
        if embedding_provider is not None:
            self.embedding_provider = embedding_provider
        if thinking_enabled is not None:
            self.thinking_enabled = bool(thinking_enabled)

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )

    def record_agent_prompt(
        self,
        agent_id: str,
        system: str,
        user: str,
        raw_response: str,
        character_response: str = "",
    ) -> None:
        self.agent_prompts[agent_id] = {
            "system": system,
            "user": user,
            "raw_response": raw_response,
            "character_response": character_response,
            "god_kind": None,
            "god_reason": None,
            "god_raw": None,
            "god_tool": None,
        }

    def public_config(self) -> Dict[str, Any]:
        return {
            "base_url": self.base_url,
            "api_key": mask_secret(self.api_key) if self.api_key and self.api_key != "sk-placeholder" else "",
            "model": self.model,
            "embedding_base_url": self.embedding_base_url,
            "embedding_api_key": mask_secret(self.embedding_api_key),
            "embedding_model": self.embedding_model or "gemini-embedding-2",
            "embedding_provider": self.embedding_provider or "google",
            "thinking_enabled": self.thinking_enabled,
            "has_api_key": bool(self.api_key and self.api_key != "sk-placeholder"),
        }

    def serializable_config(self) -> Dict[str, Any]:
        return {
            "base_url": self.base_url,
            "api_key": self.api_key if self.api_key != "sk-placeholder" else "",
            "model": self.model,
            "embedding_base_url": self.embedding_base_url,
            "embedding_api_key": self.embedding_api_key,
            "embedding_model": self.embedding_model,
            "embedding_provider": self.embedding_provider,
            "thinking_enabled": self.thinking_enabled,
        }

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: Type[BaseModel],
        max_retries: int = 3,
        temperature: float = 0.3
    ) -> Optional[Any]:
        """
        带重试和结构化校验的大模型调用
        """
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        self.last_raw_response = ""
        raw_content = ""
        for attempt in range(max_retries):
            try:
                # 兼容 Pydantic V1 和 V2 的 schema 提取
                schema_json = response_model.schema_json() if hasattr(response_model, 'schema_json') else json.dumps(response_model.model_json_schema())

                sys_msg = (
                    f"{system_prompt}\n\n"
                    f"CRITICAL: You MUST return ONLY valid JSON matching this schema:\n{schema_json}\n"
                    f"Do not wrap the JSON in markdown code blocks, just return the raw JSON string."
                )
                self.last_system_prompt = sys_msg

                async with self.semaphore:
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": sys_msg},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=temperature,
                        response_format={"type": "json_object"}
                    )

                raw_content = response.choices[0].message.content.strip()
                self.last_raw_response = raw_content

                # 清理可能残留的 markdown 标记
                if raw_content.startswith("```json"):
                    raw_content = raw_content[7:]
                if raw_content.endswith("```"):
                    raw_content = raw_content[:-3]
                raw_content = raw_content.strip()
                self.last_raw_response = raw_content

                # 尝试解析并验证
                parsed_data = response_model.parse_raw(raw_content) if hasattr(response_model, 'parse_raw') else response_model.model_validate_json(raw_content)
                return parsed_data

            except (ValidationError, json.JSONDecodeError) as e:
                print(f"[Gateway] Attempt {attempt+1}/{max_retries} JSON Validation Failed: {e}")
                if attempt == max_retries - 1:
                    print(f"[Gateway] Max retries reached. Raw output: {raw_content}")
                    return None

                # 【核心修复】：闭环自纠错，将报错反馈给下一轮的 Prompt
                user_prompt += f"\n\n[SYSTEM ERROR]: Previous attempt failed with:\n{str(e)}\nFix the JSON structure and try again."
                self.last_user_prompt = user_prompt

                await asyncio.sleep(2 ** attempt) # 指数退避

            except Exception as e:
                print(f"[Gateway] Attempt {attempt+1}/{max_retries} API Request Failed: {e}")
                if attempt == max_retries - 1:
                    return None
                await asyncio.sleep(2 ** attempt)

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        max_retries: int = 3,
        temperature: float = 0.3
    ) -> str:
        """
        带重试的普通文本大模型调用（兼容不强制要求 JSON 的旧模块）
        """
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        self.last_raw_response = ""
        for attempt in range(max_retries):
            try:
                async with self.semaphore:
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=temperature
                    )
                text = response.choices[0].message.content.strip()
                self.last_raw_response = text
                return text
            except Exception as e:
                print(f"[Gateway] Text Generation Attempt {attempt+1}/{max_retries} Failed: {e}")
                if attempt == max_retries - 1:
                    return ""
        return ""

_gateway_instance: Optional[AsyncLLMGateway] = None

def get_gateway() -> AsyncLLMGateway:
    """获取 AsyncLLMGateway 懒加载单例，消除模块导入时的顶层副作用。"""
    global _gateway_instance
    if _gateway_instance is None:
        _gateway_instance = AsyncLLMGateway()
    return _gateway_instance


def reconfigure_gateway(**kwargs) -> AsyncLLMGateway:
    gw = get_gateway()
    gw.reconfigure(**kwargs)
    return gw


def reset_gateway() -> AsyncLLMGateway:
    """Replace the singleton. Tests should call this before constructing a new SessionManager."""
    global _gateway_instance
    _gateway_instance = AsyncLLMGateway()
    return _gateway_instance


def __getattr__(name: str) -> Any:
    """保持向后兼容：当外部直接 from core.gateway import gateway 时动态解析单例。"""
    if name == "gateway":
        return get_gateway()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
