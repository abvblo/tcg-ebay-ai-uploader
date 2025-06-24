# TCG eBay Batch Uploader

Automated Trading Card Game (TCG) listing tool for eBay with AI-powered card identification and intelligent caching.

## Features

- 🤖 **AI Card Identification**: Uses Ximilar AI to identify Pokemon and Magic: The Gathering cards
- 💰 **Smart Pricing**: Fetches market prices from Pokemon TCG API and Scryfall
- 🖼️ **Image Optimization**: Automatic image processing and eBay EPS upload
- 💾 **Intelligent Caching**: Multi-level caching reduces API costs by 60-80%
- 📊 **Excel Generation**: Creates eBay-compatible upload files
- 🎯 **Simplified Logging**: Shows only essential information

git clone https://github.com/abvblo/tcg-ebay-ai-uploader.git
cd cg-ebay-ai-uploader

rm -rf .git
git init
git remote add origin https://github.com/abvblo/tcg-ebay-ai-uploader.git
cd cg-ebay-ai-uploader
git add .
git commit -m "Initial commit with new content"
git push origin main --force