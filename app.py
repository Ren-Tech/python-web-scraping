from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import time

app = Flask(__name__)

# Set up the SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///scraped_data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database model for storing scraped data
class ScrapedData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(200), nullable=False)
    headlines = db.Column(db.Text, nullable=True)
    paragraphs = db.Column(db.Text, nullable=True)
    links = db.Column(db.Text, nullable=True)
    images = db.Column(db.Text, nullable=True)
    sentiment_score = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f'<ScrapedData {self.url}>'

# Create the database tables (run this once)
with app.app_context():
    db.create_all()

# Function to check robots.txt permission
def is_scraping_allowed(url):
    parsed_url = urlparse(url)
    robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"

    try:
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        
        # Check if the page allows scraping
        return rp.can_fetch("*", url)
    except Exception:
        return True  # Assume allowed if robots.txt can't be fetched

# Sentiment analysis function
def sentiment_analysis(text):
    positive_words = ["good", "excellent", "amazing", "positive", "great", "happy"]
    negative_words = ["bad", "poor", "terrible", "negative", "sad", "worst"]
    
    positive_count = sum(word in text.lower() for word in positive_words)
    negative_count = sum(word in text.lower() for word in negative_words)

    if positive_count > negative_count:
        return f"Positive ({positive_count} positive words)"
    elif negative_count > positive_count:
        return f"Negative ({negative_count} negative words)"
    else:
        return "Neutral"

# Function to scrape website data and save to the database
def scrape_website(url):
    if not is_scraping_allowed(url):
        return {"error": "Scraping is not allowed for this website as per robots.txt."}

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        time.sleep(2)  # Throttling to prevent overloading the server
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract data
        headlines = [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3'])]
        paragraphs = [p.get_text(strip=True) for p in soup.find_all('p')]
        links = [a['href'] for a in soup.find_all('a', href=True)]
        images = [img['src'] for img in soup.find_all('img', src=True)]

        # Combine text for sentiment analysis
        all_text = ' '.join(paragraphs + headlines)
        sentiment = sentiment_analysis(all_text)

        # Save data to database
        new_data = ScrapedData(
            url=url,
            headlines='\n'.join(headlines),
            paragraphs='\n'.join(paragraphs),
            links='\n'.join(links),
            images='\n'.join(images),
            sentiment_score=sentiment
        )
        db.session.add(new_data)
        db.session.commit()

        data = {
            'url': url,
            'headlines': headlines,
            'paragraphs': paragraphs,
            'links': links,
            'images': images,
            'sentiment_score': sentiment
        }

        return data

    except requests.exceptions.HTTPError as e:
        return {"error": f"HTTP Error: {e}"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request Error: {e}"}
    except Exception as e:
        return {"error": f"An error occurred: {e}"}

@app.route('/', methods=['GET', 'POST'])
def index():
    scraped_data = {}
    if request.method == 'POST':
        website_url = request.form['website_url']
        scraped_data = scrape_website(website_url)
    return render_template('index.html', data=scraped_data)

if __name__ == '__main__':
    app.run(debug=True)
