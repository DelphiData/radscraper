pip install requests beautifulsoup4
"""
Radiopaedia Scraper using BeautifulSoup
Specific implementation for gathering 'case' and 'article' types.
"""
import re
import json
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, Any, List
from datetime import datetime

# Import your models
from src.models.case import Case, Image as CaseImage
from src.models.article import Article, ArticleSection, ArticleImage

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def scrape_case(url: str) -> Case:
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    # 1. Metadata & Source ID
    # Finding rID in metadata section: e.g. <div class="row rid">...8654</div>
    rid_div = soup.select_one('.row.rid .col-sm-8')
    source_id = f"rID-{clean_text(rid_div.text)}" if rid_div else "unknown"

    # Dates
    date_el = soup.select_one('time.date')
    created_at = date_el['datetime'] if date_el and date_el.has_attr('datetime') else datetime.utcnow().isoformat()

    # 2. Basic Info
    title = clean_text(soup.select_one('h1.header-title').text) if soup.select_one('h1.header-title') else "Untitled"
    
    # Body System / Modality (In tags section)
    # Systems are usually in .meta-item-systems
    system_el = soup.select_one('.meta-item-systems .col-sm-8 a')
    body_system = clean_text(system_el.text) if system_el else "Unknown"
    
    # Tags
    tags = [clean_text(a.text) for a in soup.select('.meta-item-tags .col-sm-8 a')]

    # 3. Patient Data
    patient = {
        "age": None,
        "age_unit": "years",
        "sex": None,
        "other": None
    }
    patient_data = soup.select_one('#case-patient-data')
    if patient_data:
        for item in patient_data.select('.data-item'):
            label = clean_text(item.select_one('.data-item-label').text).lower()
            value = clean_text(item.text).replace(item.select_one('.data-item-label').text, '')
            if 'age' in label:
                # Extract number
                nums = re.findall(r'\d+', value)
                if nums:
                    patient['age'] = int(nums[0])
            elif 'gender' in label or 'sex' in label:
                patient['sex'] = value.lower()

    # 4. Clinical Presentation (Often inferred or in specific section)
    # Radiopaedia doesn't always strictly separate this, sometimes it's the first text block.
    # We will look for a "Patient presentation" header or default to first text.
    presentation = "Not explicitly stated"
    # Logic: Look for text before "Patient Data" or specific headers.
    # For now, we leave as placeholder or advanced parsing needed.
    
    # 5. Diagnosis
    diagnosis_div = soup.select_one('.diagnostic-certainty-container')
    diagnosis = {
        "text": title, # Usually the title is the diagnosis in solved cases
        "certainty": clean_text(diagnosis_div.text) if diagnosis_div else "unknown"
    }

    # 6. Narrative (Findings & Discussion)
    narrative = {
        "findings": "",
        "impression": "", # Often mixed in discussion
        "discussion": ""
    }
    
    findings_div = soup.select_one('.study-findings.body')
    if findings_div:
        narrative['findings'] = clean_text(findings_div.text)

    discussion_div = soup.select_one('#case-discussion')
    if discussion_div:
        narrative['discussion'] = clean_text(discussion_div.text)

    # 7. Images
    # Note: High-res images are loaded via JS. We grab the specific valid carousel images.
    images = []
    carousel_items = soup.select('._StudyCarouselHeader_ImageListItem img')
    for idx, img in enumerate(carousel_items):
        src = img.get('src')
        if not src: continue
        
        # Determine modality/plane from tags or generic
        # This is a simplification; extracting specific plane per image requires parsing the hidden JSON data
        images.append(CaseImage(
            image_id=f"{source_id}_img_{idx+1}",
            modality="Unknown", # Requires deep JSON parsing
            plane="Unknown", 
            filepath=src,
            caption=f"Image {idx+1} from case",
            annotations={}
        ))

    return Case(
        source="radiopaedia",
        source_id=source_id,
        title=title,
        body_system=body_system,
        body_part="Unknown", # Hard to map perfectly without huge lookup table
        modality=["CT" if "ct" in tags else "X-ray"], # Heuristic
        clinical_presentation=presentation,
        diagnosis=diagnosis,
        narrative=narrative,
        images=images,
        tags=tags,
        metadata={
            "created_at": created_at,
            "url": url,
            "license": "See Radiopaedia ToS"
        }
    )

def scrape_article(url: str) -> Article:
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    # Basic Info
    title = clean_text(soup.select_one('h1.header-title').text)
    
    rid_div = soup.select_one('.row.section-end.rid .col-sm-8')
    source_id = f"rID-{clean_text(rid_div.text)}" if rid_div else "unknown"

    system_el = soup.select_one('.meta-item-systems .col-sm-8 a')
    body_system = clean_text(system_el.text) if system_el else "Unknown"

    # Sections
    sections = []
    content_div = soup.select_one('.body.user-generated-content')
    if content_div:
        current_section = {"title": "Introduction", "text": []}
        
        for child in content_div.children:
            if child.name in ['h2', 'h3', 'h4']:
                # Save previous
                if current_section["text"]:
                    sections.append(ArticleSection(
                        slug=current_section['title'].lower().replace(' ', '_'),
                        title=current_section['title'],
                        markdown="\n".join(current_section['text'])
                    ))
                # Start new
                current_section = {"title": clean_text(child.text), "text": []}
            elif child.name == 'p':
                current_section['text'].append(clean_text(child.text))
            elif child.name == 'ul':
                items = [f"- {li.text}" for li in child.find_all('li')]
                current_section['text'].extend(items)
        
        # Append last
        if current_section["text"]:
             sections.append(ArticleSection(
                slug=current_section['title'].lower().replace(' ', '_'),
                title=current_section['title'],
                markdown="\n".join(current_section['text'])
            ))

    # Images (from sidebar JSON)
    images = []
    # Found in <div class="hidden data"> inside .SidebarStudyViewer
    viewer_data = soup.select_one('.SidebarStudyViewer .hidden.data')
    if viewer_data:
        try:
            data = json.loads(viewer_data.text)
            for item in data.get('inclusions', []):
                images.append(ArticleImage(
                    image_id=str(item.get('imageId', 'unknown')),
                    figure_label=None,
                    modality="Unknown",
                    plane=None,
                    caption=item.get('caption', ''),
                    filepath=item.get('thumbnail', '')
                ))
        except:
            pass # JSON parse fail

    tags = [clean_text(a.text) for a in soup.select('.meta-item-tags .col-sm-8 a')]

    return Article(
        source="radiopaedia",
        source_id=source_id,
        type="article",
        title=title,
        body_system=body_system,
        body_part=None,
        sections=sections,
        images=images,
        tags=tags,
        metadata={
            "created_at": datetime.utcnow().isoformat(),
            "url": url,
            "license": "See Radiopaedia ToS"
        }
    )
