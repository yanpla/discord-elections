import settings
import discord
from discord.ext import commands
from nomination import Nomination

logger = settings.logging.getLogger("bot")
nominees = Nomination()

class ElectionSelect(discord.ui.Select):
    def __init__(self, nominee_list):
        options = [discord.SelectOption(label=nominee[1], value=str(nominee[0])) for nominee in nominee_list]
        super().__init__(options=options, placeholder="Select a nominee", max_values=1)

    async def callback(self, interaction: discord.Interaction):
        selected_nominee_id = int(self.values[0])
        nominees.record_vote(interaction.user, selected_nominee_id)
        selected_nominee = interaction.guild.get_member(selected_nominee_id)
        await interaction.response.send_message(f"You selected {selected_nominee.display_name}", ephemeral=True)

class ElectionView(discord.ui.View):
    def __init__(self, nominee_list):
        super().__init__(timeout=28800) # 8 hours
        self.add_item(ElectionSelect(nominee_list))
    
    async def on_timeout(self):
        logger.info("ElectionView timed out")
        self.clear_items()

def run():
    intents = discord.Intents.default()
    intents.members = True

    bot = commands.Bot(command_prefix=".", intents=intents)

    @bot.event
    async def on_ready():
        logger.info(f"User: {bot.user} (ID: {bot.user.id})")
        logger.info("Bot is ready to go!")
        bot.tree.copy_global_to(guild=settings.GUILDS_ID)
        await bot.tree.sync(guild=settings.GUILDS_ID)

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

    @bot.tree.command(description="Start a poll for electing a new dictator", name="startpoll")
    async def start_poll(interaction: discord.Interaction):
        # Get the list of nominees
        nominee_list = nominees.get_nominations()  # Fetch the list of nominees from your database or wherever they are stored

        # Create the ElectionSelect dropdown with the list of nominees
        view = ElectionView(nominee_list)

        # Send the message with the dropdown and initial vote count embed
        await interaction.response.send_message("Select a nominee to vote on:", view=view)

    @bot.tree.command(description="End the Election and announce the winner", name="endpoll")
    async def end_poll(interaction: discord.Interaction):
        nominee_votes = nominees.get_votes()  # Fetch the vote count from your database or wherever it is stored
        total_votes = sum(nominee_votes.values())  # Calculate the total number of votes

        # Sort the nominee_votes dictionary by vote count in descending order
        sorted_nominee_votes = {k: v for k, v in sorted(nominee_votes.items(), key=lambda item: item[1], reverse=True)}

        # Create an embed to display the vote count
        embed = discord.Embed(title="Current Vote Count", color=0x00ff00)

        # Add each nominee's vote count and percentage to the embed
        for nominee_id, votes in sorted_nominee_votes.items():
            nominee = interaction.guild.get_member(int(nominee_id))
            if nominee:
                # Calculate the percentage of votes for the nominee
                if total_votes > 0:
                    percentage = (votes / total_votes) * 100
                else:
                    percentage = 0
                embed.add_field(name=nominee.display_name, value=f"Votes: {votes} ({percentage:.2f}%)", inline=False)
        
        # Find the member(s) with the most votes
        max_votes = max(sorted_nominee_votes.values())
        winners = [interaction.guild.get_member(int(nominee_id)) for nominee_id, votes in sorted_nominee_votes.items() if votes == max_votes]

        if len(winners) == 1:
            # Send a message announcing the winner
            await interaction.response.send_message(f"The winner is {winners[0].display_name} with {max_votes} votes!", embed=embed)
        else:
            # Send a message announcing the draw
            await interaction.response.send_message("It's a draw! The election resulted in a tie.", embed=embed)
        nominees.clear_nominations()
        nominees.clear_votes()
    
    bot.run(settings.DISCORD_API_SECRET, root_logger=True)


if __name__ == "__main__":
    run()
