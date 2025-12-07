from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import json

@dataclass
class ArticleSection:
    slug: str
    title: str
    markdown: str

@dataclass
class ArticleImage:
    image_id: str
    figure_label: Optional[str]
    modality: Optional[str]
    plane: Optional[str]
    caption: str
    filepath: str

@dataclass
class Article:
    source: str
    source_id: str
    type: str
    title: str
    body_system: str
    body_part: Optional[str]
    sections: List[ArticleSection]
    images: List[ArticleImage]
    tags: List[str]
    metadata: Dict[str, Any]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)
