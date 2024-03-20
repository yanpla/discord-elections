from typing import Final
import os
from dotenv import load_dotenv
from discord import Intents, Client, Message
from responses import get_response
from discord.ext import commands
import discord
from nomination import Nomination
from datetime import datetime, timedelta


load_dotenv()
TOKEN: Final[str] = os.getenv("DISCORD_TOKEN")

intents: Intents = Intents.default()
intents.message_content = True
client: commands.Bot = commands.Bot(command_prefix=".",intents=intents)

nomination = Nomination()

@client.command()
async def nominate(ctx, candidate: discord.Member):
    # Check if the nominated candidate is a bot
    if candidate.bot:
        await ctx.send("Bots cannot be nominated.")
        return
    
    # Check if the nomination period is open
    if not is_nomination_period_open():
        await ctx.send("The nomination period is closed.")
        return

    # Check if the candidate is already nominated
    if nomination.is_candidate_nominated(candidate):
        await ctx.send(f"{candidate.display_name} is already nominated.")
        return

    # Nominate the candidate
    nomination.nominate_candidate(candidate)

    await ctx.send(f"{candidate.display_name} has been nominated.")

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')

# Define function to check if nominations are open
def is_nomination_period_open():
    today = datetime.now()
    first_day_of_month = today.replace(day=1)
    days_until_first_monday = (7 - first_day_of_month.weekday()) % 7  # Number of days until the first Monday
    first_monday = first_day_of_month + timedelta(days=days_until_first_monday)
    friday = first_monday + timedelta(days=4)  # Friday is 4 days after Monday
    return first_monday <= today <= friday

def main():
    client.run(TOKEN)

if __name__ == '__main__':
    main()