# Number Info Bot

A Telegram bot that provides phone number information using an external API and stores data in MongoDB.

## Features

* Phone number information lookup
* MongoDB database support
* Channel join verification
* Admin support
* Environment variable configuration
* Easy deployment on Railway

## Project Structure

```text
numToinfo/
│
├── .env
├── .gitignore
├── bot.py
├── requirements.txt
└── README.md
```

## Environment Variables

Create a `.env` file and configure the following variables:

```env
BOT_TOKEN=
CHANNEL_INVITE_LINK=
CHANNEL_ID=
API_URL=
API_KEY=
MONGODB_URI=
ADMIN_IDS=
OWNER_USERNAME=
DB_NAME=
```

### Example Configuration

```env
BOT_TOKEN=YOUR_BOT_TOKEN
CHANNEL_INVITE_LINK=CHANNEL_LINK
CHANNEL_ID=-1001234567890
API_URL=API_LINK
API_KEY=YOUR_API_KEY
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
ADMIN_IDS=123456789
OWNER_USERNAME=your_username
DB_NAME=number_info_bot
```

## Installation

Clone the repository:

```bash
git clone https://github.com/officialDangerboy/num-to-info-bot.git
cd numToinfo
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the Bot

```bash
python bot.py
```


### 1. Deploy on Railway

* Create a Railway account.
* Create a new project.
* Select "Deploy from GitHub Repo".
* Choose your repository.

### 3. Add Variables

In Railway Dashboard:

```text
Project → Variables
```

Add all variables from your `.env` file.

### 4. Start Command

```bash
python bot.py
```

## requirements.txt Example

```txt
python-telegram-bot
pymongo
python-dotenv
requests
```

## Security

* Never commit `.env` files.
* Never expose API keys or bot tokens.
* Keep MongoDB credentials private.
* Add `.env` to `.gitignore`.

## License

This project is provided for educational purposes.
