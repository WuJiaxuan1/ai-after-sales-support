"""
rag.py — 轻量 RAG 检索引擎（v2）
================================
MVP 保持内存 TF-IDF，不引入额外向量数据库依赖。
修复旧版中文“整句作为一个 token”导致检索几乎失效的问题：
  - 中文单字 + 二元字符片段
  - 英文 / 数字按单词

普通售后 RAG 与 Safety RAG 使用两个独立 RAGEngine 实例，加载不同知识文件。
"""
import math
import re
from collections import Counter
from typing import List

from ..models.schemas import RAGResult


class KnowledgeChunk:
    def __init__(self, source_id, source_title, source_version, chunk_id, content):
        self.source_id = source_id
        self.source_title = source_title
        self.source_version = source_version
        self.chunk_id = chunk_id
        self.content = content
        self.tokens = self._tokenize(content)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """中文用单字+二元字符，英文按单词，兼顾召回与简单实现。"""
        text = (text or "").lower()
        tokens: List[str] = []

        for block in re.findall(r'[\u4e00-\u9fff]+', text):
            chars = list(block)
            tokens.extend(chars)
            tokens.extend(block[i:i + 2] for i in range(len(block) - 1))

        tokens.extend(re.findall(r'[a-z0-9]+', text))
        return tokens


class RAGEngine:
    def __init__(self, name: str = "rag"):
        self.name = name
        self._chunks: List[KnowledgeChunk] = []
        self._idf = {}
        self._dirty = True

    def add_chunk(self, source_id, source_title, source_version, chunk_id, content):
        if not chunk_id or not content:
            return
        self._chunks.append(KnowledgeChunk(source_id, source_title, source_version, chunk_id, content))
        self._dirty = True

    def load_from_markdown(self, filepath: str):
        """解析每个 `### K-...` 知识片段及其 metadata。"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
        except FileNotFoundError:
            return

        sections = re.split(r'(?=^###\s+K-[^\n]+)', text, flags=re.MULTILINE)
        for section in sections:
            if not section.lstrip().startswith("### K-"):
                continue
            source_id = self._meta(section, "source_id")
            source_title = self._meta(section, "source_title")
            source_version = self._meta(section, "source_version")
            chunk_id = self._meta(section, "chunk_id")
            if not chunk_id:
                continue

            body_lines = []
            for line in section.splitlines():
                if line.startswith("### K-"):
                    continue
                if re.match(r'-\s+(source_id|source_title|source_version|chunk_id):', line):
                    continue
                body_lines.append(line)
            content = "\n".join(body_lines).strip()
            self.add_chunk(source_id, source_title, source_version, chunk_id, content)

    @staticmethod
    def _meta(section: str, key: str) -> str:
        m = re.search(r'^-\s+{}:\s*(.+)$'.format(re.escape(key)), section, flags=re.MULTILINE)
        return m.group(1).strip() if m else ""

    def retrieve(self, query: str, top_k: int = 3, threshold: float = 0.01) -> List[RAGResult]:
        if not self._chunks:
            return []
        if self._dirty:
            self._rebuild_idf()

        query_tokens = KnowledgeChunk._tokenize(query)
        if not query_tokens:
            return []

        query_tf = Counter(query_tokens)
        query_vec = {t: (1 + math.log(c)) * self._idf.get(t, 1.0) for t, c in query_tf.items()}

        scored = []
        for chunk in self._chunks:
            chunk_tf = Counter(chunk.tokens)
            chunk_vec = {t: (1 + math.log(c)) * self._idf.get(t, 1.0) for t, c in chunk_tf.items()}
            score = self._cosine(query_vec, chunk_vec)
            if score >= threshold:
                scored.append((score, chunk))

        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            RAGResult(
                source_id=chunk.source_id,
                source_title=chunk.source_title,
                source_version=chunk.source_version,
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                score=round(score, 4),
            )
            for score, chunk in scored[:top_k]
        ]

    def _rebuild_idf(self):
        n = len(self._chunks)
        if n == 0:
            self._idf = {}
            self._dirty = False
            return
        df = {}
        for chunk in self._chunks:
            for token in set(chunk.tokens):
                df[token] = df.get(token, 0) + 1
        self._idf = {token: math.log((n + 1) / (count + 1)) + 1 for token, count in df.items()}
        self._dirty = False

    @staticmethod
    def _cosine(a: dict, b: dict) -> float:
        common = set(a) & set(b)
        if not common:
            return 0.0
        dot = sum(a[k] * b[k] for k in common)
        mag_a = math.sqrt(sum(v * v for v in a.values()))
        mag_b = math.sqrt(sum(v * v for v in b.values()))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)
