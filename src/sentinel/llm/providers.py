from typing import Protocol
import httpx
import asyncio,threading
MODEL_LOCK=threading.Lock()
async def acquire_model():
    while not MODEL_LOCK.acquire(blocking=False):await asyncio.sleep(.1)
class LLMProvider(Protocol):
    async def chat(self,messages:list[dict])->str:...
class OllamaProvider:
    def __init__(self,s):self.s=s
    async def chat(self,messages):
        await acquire_model()
        try:return await self._chat(messages)
        finally:MODEL_LOCK.release()
    async def _chat(self,messages):
        async with httpx.AsyncClient(timeout=180) as c:
            r=await c.post(self.s.llm_base_url+"/api/chat",json={"model":self.s.llm_model,"messages":messages,"stream":False,"think":False,"keep_alive":"5m","options":{"temperature":0,"num_predict":800,"num_ctx":8192}})
            r.raise_for_status(); return r.json()["message"]["content"]
    async def vision(self,messages,schema):
        await acquire_model()
        try:
            async with httpx.AsyncClient(timeout=180) as c:
                show=await c.post(self.s.llm_base_url+'/api/show',json={'model':self.s.llm_model});show.raise_for_status()
                if 'vision' not in show.json().get('capabilities',[]):raise ValueError('O modelo configurado não aceita imagens.')
                r=await c.post(self.s.llm_base_url+'/api/chat',json={'model':self.s.llm_model,'messages':messages,'format':schema,'stream':False,'think':False,'keep_alive':'5m','options':{'temperature':0,'num_predict':1000,'num_ctx':16384}})
                r.raise_for_status();return r.json()['message']['content']
        finally:MODEL_LOCK.release()
class CompatibleProvider:
    def __init__(self,s):self.s=s
    async def chat(self,messages):
        await acquire_model()
        try:return await self._chat(messages)
        finally:MODEL_LOCK.release()
    async def _chat(self,messages):
        async with httpx.AsyncClient(timeout=180) as c:
            r=await c.post(self.s.llm_base_url.rstrip("/")+"/chat/completions",headers={"Authorization":"Bearer "+self.s.llm_api_key},json={"model":self.s.llm_model,"messages":messages,"temperature":0,"max_tokens":800})
            r.raise_for_status(); return r.json()["choices"][0]["message"]["content"]
