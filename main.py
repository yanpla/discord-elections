import settings
import discord
from discord.ext import commands
from discord import app_commands
from nomination import Nomination
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import datetime
from apscheduler.triggers.date import DateTrigger

logger = settings.logging.getLogger("bot")
nominees = Nomination()


class ElectionBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.presences = True
        super().__init__(command_prefix=".", intents=intents)
        self.scheduler = AsyncIOScheduler()
        self.schedule_data = self._load_schedule_data()

        self.guild_object = discord.Object(id=settings.GUILDS_ID)

        # Register commands directly in the class
        self.tree.command(
            name="nominateme", description="Nominate yourself", guild=self.guild_object
        )(self.nominateme)
        self.tree.command(
            name="force_start_nominations",
            description="ADMIN: Start nomination period immediately",
            guild=self.guild_object,
        )(self.force_start_nominations)

        self.tree.command(
            name="force_start_voting",
            description="ADMIN: Start voting period immediately",
            guild=self.guild_object,
        )(self.force_start_voting)

        self.tree.command(
            name="force_end_election",
            description="ADMIN: End election immediately",
            guild=self.guild_object,
        )(self.force_end_election)

        self.tree.command(
            name="schedule",
            description="View the election schedule",
            guild=self.guild_object,
        )(self.view_schedule)

    def _load_schedule_data(self):
        try:
            with open("last_election.txt", "r") as f:
                last_timestamp = int(f.read().strip())
                last_date = datetime.datetime.fromtimestamp(last_timestamp)
                return {
                    "last_election": last_date,
                    "next_election": last_date + datetime.timedelta(weeks=10),
                }
        except (FileNotFoundError, ValueError):
            return {}

    def _save_schedule_data(self):
        if "last_election" in self.schedule_data:
            with open("last_election.txt", "w") as f:
                timestamp = int(self.schedule_data["last_election"].timestamp())
                f.write(str(timestamp))

    def _update_schedule(self, key, when):
        self.schedule_data[key] = when
        if key == "nomination_start":
            self.schedule_data["last_election"] = when
            self._save_schedule_data()

    async def setup_hook(self):
        await self.tree.sync(guild=self.guild_object)
        self.scheduler.start()

        # Check for existing voting phases
        now = datetime.datetime.now()
        if "voting_end" in self.schedule_data:
            if self.schedule_data["voting_end"] > now:
                self._schedule_job(
                    "end_voting", self.schedule_data["voting_end"], self.end_voting
                )
            else:
                await self.end_voting()

        elif "voting_start" in self.schedule_data:
            if self.schedule_data["voting_start"] > now:
                self._schedule_job(
                    "start_voting",
                    self.schedule_data["voting_start"],
                    self.start_voting,
                )
            else:
                await self.start_voting()

        elif "nomination_close" in self.schedule_data:
            if self.schedule_data["nomination_close"] > now:
                self._schedule_job(
                    "close_nominations",
                    self.schedule_data["nomination_close"],
                    self.close_nominations,
                )
            else:
                await self.close_nominations()

        else:
            await self.schedule_elections()

    async def schedule_elections(self):
        # Use schedule data instead of reading file directly
        if "next_election" in self.schedule_data:
            next_date = self.schedule_data["next_election"]
            if next_date > datetime.datetime.now():
                self._schedule_job("election_cycle", next_date, self.open_nominations)
                self._update_schedule("nomination_start", next_date)
                return

        # Fallback to default Monday scheduling
        next_monday = self.get_next_monday()
        self._schedule_job("election_cycle", next_monday, self.open_nominations)
        self._update_schedule("nomination_start", next_monday)

    def _schedule_job(self, job_id, when, func):
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        self.scheduler.add_job(func, trigger=DateTrigger(when), id=job_id)

        if not self.scheduler.running:
            self.scheduler.start()

    def get_next_monday(self):
        today = datetime.datetime.now()
        days_ahead = (0 - today.weekday() + 7) % 7  # 0 is Monday
        next_monday = today + datetime.timedelta(days=days_ahead)
        return next_monday.replace(hour=0, minute=0, second=0, microsecond=0)

    async def open_nominations(self):
        # Update schedule data instead of writing directly to file
        current_time = datetime.datetime.now()
        self.schedule_data["last_election"] = current_time
        self._save_schedule_data()

        # Clear existing jobs first
        for job_id in ["close_nominations", "start_voting", "end_voting"]:
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
        nominees.open_nomination_period()
        announcement_channel = self.get_channel(settings.CHANNEL_ID)

        # Schedule close for Thursday 23:59
        thursday = self.get_next_monday() + datetime.timedelta(
            days=3, hours=23, minutes=59
        )
        self.scheduler.add_job(
            self.close_nominations,
            trigger=DateTrigger(thursday),
            id="close_nominations",
        )
        self._update_schedule("nomination_close", thursday)

        thursday_ts = int(thursday.timestamp())
        await announcement_channel.send(
            f"🏛️ @everyone De nominatieronde is geopend! Gebruik `/nominateme`  om jezelf te nomineren.\n"
            f"🗓️ Sluit op <t:{thursday_ts}:F> (<t:{thursday_ts}:R>)",
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )

    async def close_nominations(self):
        if self.scheduler.get_job("close_nominations"):
            self.scheduler.remove_job("close_nominations")
        nominees.close_nomination_period()
        announcement_channel = self.get_channel(settings.CHANNEL_ID)
        await announcement_channel.send(
            "⛔ Nominaties gesloten. Stemmen begint morgen!"
        )

        # Schedule voting for Friday 00:00
        now = datetime.datetime.now()
        friday = (now + datetime.timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        self.scheduler.add_job(
            self.start_voting, trigger=DateTrigger(friday), id="start_voting"
        )
        self._update_schedule("voting_start", friday)

    async def start_voting(self):
        if self.scheduler.get_job("start_voting"):
            self.scheduler.remove_job("start_voting")

        nominee_list = nominees.get_nominations()
        if not nominee_list:
            channel = self.get_channel(settings.CHANNEL_ID)
            await channel.send("❌ No nominees. Election canceled.")
            return

        election_channel = self.get_channel(settings.CHANNEL_ID)
        view = ElectionView(nominee_list)

        # Schedule vote closing in 24 hours
        self.scheduler.add_job(
            self.end_voting,
            trigger=DateTrigger(datetime.datetime.now() + datetime.timedelta(hours=24)),
            id="end_voting",
        )
        end_time = datetime.datetime.now() + datetime.timedelta(hours=24)
        self._update_schedule("voting_end", end_time)
        end_ts = int(end_time.timestamp())
        self.vote_message = await election_channel.send(
            f"🗳️ @everyone Stem op de nieuwe dictator!\n"
            f"⏳ Stemmen eindigt op <t:{end_ts}:F> (<t:{end_ts}:R>)",
            view=view,
            allowed_mentions=discord.AllowedMentions(everyone=True),
        )

    async def end_voting(self):
        self.schedule_data = {}
        await self.vote_message.edit(view=None)
        await self.process_election_results()

    async def process_election_results(self, guild=None, channel=None):
        try:
            if not guild:
                # Use get_guild instead of fetch_guild to access cached members
                guild = self.get_guild(settings.GUILDS_ID)
                if not guild:
                    guild = await self.fetch_guild(settings.GUILDS_ID)
                    # Refresh member cache if needed
                    await guild.chunk()
            if not channel:
                channel = await guild.fetch_channel(settings.CHANNEL_ID)

            # Election processing logic
            nominee_votes = nominees.get_votes()
            total_votes = sum(nominee_votes.values())

            # Sort votes and filter valid members
            valid_winners = []
            max_votes = 0

            for nominee_id, votes in nominee_votes.items():
                member = guild.get_member(int(nominee_id))
                if member:
                    if votes > max_votes:
                        max_votes = votes
                        valid_winners = [member]
                    elif votes == max_votes:
                        valid_winners.append(member)
                else:
                    logger.warning(f"Invalid member ID in votes: {nominee_id}")

            # Create embed with results
            embed = discord.Embed(title="Verkiezingen Resultaten", color=0x00FF00)

            # Add all nominees to embed (even if they left the server)
            for nominee_id, votes in sorted(
                nominee_votes.items(), key=lambda item: item[1], reverse=True
            ):
                member = guild.get_member(int(nominee_id))
                display_name = (
                    member.display_name if member else f"Unknown Member ({nominee_id})"
                )
                percentage = (votes / total_votes * 100) if total_votes > 0 else 0
                embed.add_field(
                    name=display_name,
                    value=f"Stemmen: {votes} ({percentage:.2f}%)",
                    inline=False,
                )

            # Manage dictator role
            dictator_role = guild.get_role(settings.DICTATOR_ROLE_ID)
            if not dictator_role:
                await channel.send("Dictator role not found!")
                return

            try:
                # Remove role from current holders
                current_dictators = [
                    m for m in guild.members if dictator_role in m.roles
                ]
                for member in current_dictators:
                    await member.remove_roles(
                        dictator_role, reason="Election concluded"
                    )

                # Assign to valid winners
                result_message = "@everyone "
                if valid_winners:
                    for winner in valid_winners:
                        await winner.add_roles(dictator_role, reason="Election winner")

                    if len(valid_winners) == 1:
                        result_message += f"🏆 Jullie nieuwe dictator is: {valid_winners[0].mention} met {max_votes} stemmen!"
                    else:
                        winner_mentions = ", ".join(w.mention for w in valid_winners)
                        result_message += (
                            f"🤝 Draw between {winner_mentions} with {max_votes} votes!"
                        )
                else:
                    result_message = "⚠️ No valid winners found!"

                await channel.send(result_message, embed=embed)

            except discord.Forbidden:
                await channel.send("❌ Missing permissions to manage roles!")
            except Exception as e:
                logger.error(f"Election error: {str(e)}", exc_info=True)
                await channel.send("⚠️ Error processing results!")

        except Exception as e:
            logger.error(
                f"Critical error in election processing: {str(e)}", exc_info=True
            )
        finally:
            nominees.clear_nominations()
            nominees.clear_votes()
            await self.schedule_elections()

    async def nominateme(self, interaction: discord.Interaction):
        candidate = interaction.user
        if not nominees.is_nomination_period_open():
            await interaction.response.send_message(
                "The nomination period is closed.", ephemeral=True
            )
            return
        if nominees.is_candidate_nominated(candidate):
            await interaction.response.send_message(
                f"{candidate.display_name} is already nominated.", ephemeral=True
            )
            return

        nominees.nominate_candidate(candidate)
        await interaction.response.send_message(
            f"{candidate.display_name} has been nominated."
        )

    @app_commands.checks.has_permissions(administrator=True)
    async def force_start_nominations(self, interaction: discord.Interaction):
        """Admin command to start nominations"""
        await interaction.response.defer(ephemeral=True)
        await self.open_nominations()
        await interaction.followup.send("🗳️ Nomination period started!", ephemeral=True)

    @app_commands.checks.has_permissions(administrator=True)
    async def force_start_voting(self, interaction: discord.Interaction):
        """Admin command to start voting"""
        await interaction.response.defer(ephemeral=True)
        await self.close_nominations()
        await self.start_voting()
        await interaction.followup.send("✅ Voting period started!", ephemeral=True)

    @app_commands.checks.has_permissions(administrator=True)
    async def force_end_election(self, interaction: discord.Interaction):
        """Admin command to end election"""
        await interaction.response.defer(ephemeral=True)
        await self.end_voting()
        await interaction.followup.send("🏁 Election concluded!", ephemeral=True)

    def _format_schedule_date(self, date_key, friendly_name):
        if date_key in self.schedule_data:
            timestamp = int(self.schedule_data[date_key].timestamp())
            return f"📅 {friendly_name}: <t:{timestamp}:F> (<t:{timestamp}:R>)\n"
        return ""

    async def view_schedule(self, interaction: discord.Interaction):
        """Command to view the election schedule"""
        schedule_text = "**Election Schedule**\n\n"

        # Add scheduled events
        schedule_text += self._format_schedule_date(
            "nomination_start", "Nominations Start"
        )
        schedule_text += self._format_schedule_date(
            "nomination_close", "Nominations Close"
        )
        schedule_text += self._format_schedule_date("voting_start", "Voting Starts")
        schedule_text += self._format_schedule_date("voting_end", "Voting Ends")

        # Add next election info from schedule data
        if "next_election" in self.schedule_data:
            next_ts = int(self.schedule_data["next_election"].timestamp())
            schedule_text += (
                f"\n🔄 Next election cycle starts: <t:{next_ts}:F> (<t:{next_ts}:R>)"
            )
        else:
            schedule_text += "\n❌ No previous election data found"

        if not any(
            key in self.schedule_data
            for key in [
                "nomination_start",
                "nomination_close",
                "voting_start",
                "voting_end",
            ]
        ):
            schedule_text += "\n⚠️ No active election schedule"

        await interaction.response.send_message(schedule_text)


class ElectionSelect(discord.ui.Select):
    def __init__(self, nominee_list):
        options = [
            discord.SelectOption(label=nominee[1], value=str(nominee[0]))
            for nominee in nominee_list
        ]
        super().__init__(options=options, placeholder="Select a nominee", max_values=1)

    async def callback(self, interaction: discord.Interaction):
        selected_nominee_id = int(self.values[0])
        nominees.record_vote(interaction.user, selected_nominee_id)
        selected_nominee = interaction.guild.get_member(selected_nominee_id)
        await interaction.response.send_message(
            f"You selected {selected_nominee.display_name}", ephemeral=True
        )


class ElectionView(discord.ui.View):
    def __init__(self, nominee_list):
        super().__init__(timeout=86400)  # 24 hours
        self.add_item(ElectionSelect(nominee_list))

    async def on_timeout(self):
        logger.info("ElectionView timed out")
        self.clear_items()


def run():
    bot = ElectionBot()

    @bot.event
    async def on_ready():
        logger.info(f"User: {bot.user} (ID: {bot.user.id})")
        logger.info("Bot is ready to go!")

    bot.run(settings.DISCORD_API_SECRET, root_logger=True)


if __name__ == "__main__":
    run()
