import os
import asyncio
import json
from typing import Optional, Any, Type, Dict
from pydantic import BaseModel, ValidationError
from openai import AsyncOpenAI
from dotenv import load_dotenv

# 自动寻找项目根目录的 .env 文件
load_dotenv()

class AsyncLLMGateway:
    """
    SINA V3 统一大模型网关
    负责：并发控制、指数退避重试、JSON 强制校验、错误降级
    """
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url="https://api.deepseek.com"
        )
    
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
        for attempt in range(max_retries):
            try:
                # 兼容 Pydantic V1 和 V2 的 schema 提取
                schema_json = response_model.schema_json() if hasattr(response_model, 'schema_json') else json.dumps(response_model.model_json_schema())
                
                sys_msg = (
                    f"{system_prompt}\n\n"
                    f"CRITICAL: You MUST return ONLY valid JSON matching this schema:\n{schema_json}\n"
                    f"Do not wrap the JSON in markdown code blocks, just return the raw JSON string."
                )
                
                response = await self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": sys_msg},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=temperature,
                    response_format={"type": "json_object"}
                )
                
                raw_content = response.choices[0].message.content.strip()
                
                # 清理可能残留的 markdown 标记
                if raw_content.startswith("```json"):
                    raw_content = raw_content[7:]
                if raw_content.endswith("```"):
                    raw_content = raw_content[:-3]
                raw_content = raw_content.strip()

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
        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=temperature
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                print(f"[Gateway] Text Generation Attempt {attempt+1}/{max_retries} Failed: {e}")
                if attempt == max_retries - 1:
                    return ""
                await asyncio.sleep(2 ** attempt)

# 暴露单例供全局调用
gateway = AsyncLLMGateway()
