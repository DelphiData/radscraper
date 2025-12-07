import sys
import os

# Add parent dir to path so we can import src
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.ingestion.radiopaedia import scrape_case, scrape_article

def main():
    # Test Case
    print("Scraping Case...")
    case_url = "https://radiopaedia.org/cases/cystic-bronchiectasis-1"
    case = scrape_case(case_url)
    print(case.to_json())

    # Test Article
    print("\nScraping Article...")
    article_url = "https://radiopaedia.org/articles/cystic-bronchiectasis"
    article = scrape_article(article_url)
    print(article.to_json())

if __name__ == "__main__":
    main()
