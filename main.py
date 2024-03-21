import settings
import discord
from discord.ext import commands
from nomination import Nomination

logger = settings.logging.getLogger("bot")

class ElectionSelect(discord.ui.Select):
    def __init__(self, nominee_list):
        options = [discord.SelectOption(label=nominee.display_name, value=str(nominee.id)) for nominee in nominee_list]
        super().__init__(options=options, placeholder="Select a nominee", max_values=1)

    async def callback(self, interaction: discord.Interaction):
        selected_nominee_id = int(self.values[0])
        selected_nominee = interaction.guild.get_member(selected_nominee_id)
        await interaction.response.send_message(f"You selected {selected_nominee.display_name}")

class ElectionView(discord.ui.View):
    def __init__(self, nominee_list):
        super().__init__()
        self.add_item(ElectionSelect(nominee_list))

def run():
    intents = discord.Intents.default()
    intents.members = True

    bot = commands.Bot(command_prefix=".", intents=intents)

    @bot.event
    async def on_ready():
        logger.info(f"User: {bot.user} (ID: {bot.user.id})")
        bot.tree.copy_global_to(guild=settings.GUILDS_ID)
        await bot.tree.sync(guild=settings.GUILDS_ID)

    @bot.tree.command(description="Ping the bot", name="ping")
    async def ping(interaction: discord.Interaction):
        await interaction.response.send_message("Pong!")

    nominees = Nomination()
    @bot.tree.command(description="Nominate yourself", name="nominateme")
    async def nominateme(interaction: discord.Interaction):
        candidate = interaction.user
        # Check if the nomination period is open
        if not nominees.is_nomination_period_open():
            await interaction.response.send_message("The nomination period is closed.", ephemeral=True)
            return

        # Check if the candidate is already nominated
        if nominees.is_candidate_nominated(candidate):
            await interaction.response.send_message(f"{candidate.display_name} is already nominated.", ephemeral=True)
            return

        # Nominate the candidate
        nominees.nominate_candidate(candidate)

        await interaction.response.send_message(f"{candidate.display_name} has been nominated.")

    @bot.tree.command(description="Start a poll for electing a new nominee", name="startpoll")
    async def start_poll(interaction: discord.Interaction):
        # Get the list of nominees
        nominee_list = nominees.get_nominations()  # Fetch the list of nominees from your database or wherever they are stored

        # Create the ElectionSelect dropdown with the list of nominees
        view = ElectionView(nominee_list)

        # Send the message with the dropdown
        await interaction.response.send_message("Select a nominee to start the poll:", view=view)


    bot.run(settings.DISCORD_API_SECRET, root_logger=True)


if __name__ == "__main__":
    run()