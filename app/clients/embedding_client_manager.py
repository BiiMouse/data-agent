import asyncio
from typing import Optional

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.conf.app_config import app_config, EmbeddingConfig


class EmbeddingClientManager:
    def __init__(self,config:EmbeddingConfig):
        self.embeddings:Optional[HuggingFaceEndpointEmbeddings]=None
        self.config=config

    def _get_url(self):
        return f"http://{self.config.host}:{self.config.port}"

    def init(self):
        self.embeddings = HuggingFaceEndpointEmbeddings(model=self._get_url())

embedding_client_manager=EmbeddingClientManager(app_config.embedding)


if __name__ == '__main__':
    # 初始化客户端对象
    embedding_client_manager.init()
    # 获取客户端对象
    embeddings=embedding_client_manager.embeddings

    async def test():
        # 文档
        text = "What is deep learning?"
        # 转换向量--单个
        # [float,float]
        # result=await embeddings.aembed_query(text)
        # print(type(result))
        # print(result)
        # print(len(result))

        result=await embeddings.aembed_documents([text])
        # [[float,float....],[float,float....],[float,float....]]
        print(type(result))
        print(result)
        print(len(result))



    asyncio.run(test())








