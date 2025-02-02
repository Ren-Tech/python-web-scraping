from flask import Flask, render_template, request
from flask_sqlalchemy import SQLAlchemy
import os
import yfinance as yf
from datetime import datetime
import time
from urllib.parse import urljoin

app = Flask(__name__)

# Set up the SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///stock_data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database model for storing stock data
class StockData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    price = db.Column(db.Float, nullable=False)
    volume = db.Column(db.BigInteger, nullable=True)
    high = db.Column(db.Float, nullable=True)
    low = db.Column(db.Float, nullable=True)
    previous_close = db.Column(db.Float, nullable=True)
    change = db.Column(db.Float, nullable=True)
    change_percent = db.Column(db.Float, nullable=True)
    trend = db.Column(db.String(20), nullable=True)

    def __repr__(self):
        return f'<StockData {self.symbol}>'

# Create the database tables
with app.app_context():
    db.drop_all()
    db.create_all()

def analyze_trend(change_percent):
    if change_percent is None:
        return "Unknown"
    if change_percent > 5:
        return "Strong Bullish"
    elif change_percent > 0:
        return "Bullish"
    elif change_percent < -5:
        return "Strong Bearish"
    elif change_percent < 0:
        return "Bearish"
    else:
        return "Neutral"

def fetch_stock_data(symbol):
    try:
        # Fetch data using yfinance
        stock = yf.Ticker(symbol)
        info = stock.info
        
        if not info:
            return {"error": "No data found for the given symbol"}

        # Get current price and calculate change
        current_price = info.get('currentPrice', 0.0)
        previous_close = info.get('previousClose', 0.0)
        change = current_price - previous_close
        change_percent = (change / previous_close * 100) if previous_close else 0.0

        # Fetch news data
        news = stock.news
        processed_news = []
        for article in news[:5]:  # Get latest 5 news items
            processed_news.append({
                'title': article.get('title', ''),
                'publisher': article.get('publisher', ''),
                'link': article.get('link', ''),
                'published': datetime.fromtimestamp(article.get('providerPublishTime', 0)),
                'type': article.get('type', ''),
                'thumbnail': article.get('thumbnail', {}).get('resolutions', [{}])[0].get('url', '')
            })

        # Prepare data for database
        db_data = {
            'symbol': symbol,
            'timestamp': datetime.now(),
            'price': current_price,
            'volume': info.get('volume', 0),
            'high': info.get('dayHigh', 0.0),
            'low': info.get('dayLow', 0.0),
            'previous_close': previous_close,
            'change': change,
            'change_percent': change_percent,
            'trend': analyze_trend(change_percent)
        }

        # Save to database
        new_data = StockData(**db_data)
        db.session.add(new_data)
        db.session.commit()

        # Add additional display data
        db_data.update({
            'market_cap': info.get('marketCap', 0),
            'pe_ratio': info.get('trailingPE', None),
            'dividend_yield': info.get('dividendYield', None),
            'fifty_day_avg': info.get('fiftyDayAverage', None),
            'two_hundred_day_avg': info.get('twoHundredDayAverage', None),
            'news': processed_news,  # Add news to the response
            'company_name': info.get('longName', symbol)
        })

        return db_data

    except Exception as e:
        return {"error": f"An error occurred: {str(e)}"}

@app.route('/', methods=['GET', 'POST'])
def index():
    stock_data = {}
    if request.method == 'POST':
        stock_symbol = request.form['stock_symbol'].upper()
        frequency = int(request.form.get('frequency', 5))
        stock_data = fetch_stock_data(stock_symbol)
    return render_template('index.html', data=stock_data)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)