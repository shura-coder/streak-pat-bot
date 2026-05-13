<p align="center">
  <img src="" width="400">
</p>

---

<h2> The bot is designed for running timers in chat groups. It allows you to set a timer on a message:</h2>
<p align="center">
  <img src="./Знімок екрана 2026-05-10 211421.png" wight="200">
</p>

The bot is written in Python, which allows you to quite easily rebuild it for yourself. It has a pretty simple interface, so you won’t get confused. And soon, a database will be added so that if the bot stops, your timers won’t reset, but will continue running after restarting the bot, and the timer won’t be lost!! And now let's move on to running the bot:
1. Create a bot folder

For example:
```yaml
C:\tg-timer-bot
```
we throw the bot file there

2. we open the bot file and find the line:
```yaml
TOKEN = "your_Тtoken_bot"
```
3. In Telegram, go to BotFather and paste the token that it will give here:
```yaml
TOKEN = "123454156hgfjhbfjhb"
```
4. Next open the terminal in the folder

5.Install aiogram
```yaml
pip install -U aiogram
```
6.started bot
```yaml
python bot.py
```
or
```yaml 
py bot.py
