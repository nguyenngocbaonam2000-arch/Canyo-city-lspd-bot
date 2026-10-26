
import os
import sqlite3
import discord
from discord.ext import commands
from discord import app_commands

TOKEN = os.getenv("MTU2NDI0MDkzMDg5MzIwMTUyOA.G6lJ81.n4ZZezsc_a>", ").strip()
GUILD_ID = 0  # De 0 neu muon lenh dung tren moi server
ROLE_RECRUIT = "Chờ Phỏng Vấn"
ROLE_LSPD = "LSPD"
REVIEW_CHANNEL = "xet-duyet-don"
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "canyon.db")

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

db = sqlite3.connect(DB_FILE)
db.execute("""CREATE TABLE IF NOT EXISTS applications (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 user_id INTEGER, kind TEXT, data TEXT,
 status TEXT DEFAULT 'pending', callsign INTEGER UNIQUE
)""")
db.execute("""CREATE TABLE IF NOT EXISTS duty (
 user_id INTEGER PRIMARY KEY, status TEXT
)""")
db.commit()


def add_app(user_id, kind, data, callsign=None):
    cur = db.cursor()
    cur.execute(
        "INSERT INTO applications(user_id,kind,data,callsign) VALUES(?,?,?,?)",
        (user_id, kind, data, callsign)
    )
    db.commit()
    return cur.lastrowid


def get_role(guild, name):
    target = " ".join(name.split()).casefold()
    return next(
        (role for role in guild.roles
         if " ".join(role.name.split()).casefold() == target),
        None
    )


async def send_review(guild, app_id, user_id, kind, data):
    channel = discord.utils.get(
        guild.text_channels, name=REVIEW_CHANNEL
    )

    if channel is None:
        print(f"KHONG TIM THAY KENH: #{REVIEW_CHANNEL}")
        return False

    try:
        embed = discord.Embed(
            title=f"ĐƠN #{app_id} — {kind}",
            description=f"Người gửi: <@{user_id}>\\n\\n{data}",
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"Application ID: {app_id}")
        await channel.send(embed=embed, view=ReviewView())
        print(f"Da gui don #{app_id} vao #{channel.name}")
        return True
    except Exception as e:
        print(f"LOI GUI DON: {type(e).__name__}: {e}")
        return False

class ReviewView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def decide(self, interaction, approved):
        if not interaction.user.guild_permissions.manage_roles:
            return await interaction.response.send_message(
                "❌ Bạn không có quyền duyệt đơn.", ephemeral=True
            )

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            embed = interaction.message.embeds[0]
            footer = embed.footer.text or ""
            app_id = int(footer.split(":")[-1].strip().replace("#", ""))

            row = db.execute(
                "SELECT user_id,kind,data,status,callsign FROM applications WHERE id=?",
                (app_id,)
            ).fetchone()

            if not row or row[3] != "pending":
                return await interaction.followup.send(
                    "⚠️ Đơn đã được xử lý hoặc không tồn tại.", ephemeral=True
                )

            user_id, kind, data, status, callsign = row
            guild = interaction.guild
            member = guild.get_member(user_id)

            if approved and not member:
                member = await guild.fetch_member(user_id)

            if approved and member:
                if kind == "DANG KY NGANH":
                    role = get_role(guild, ROLE_RECRUIT)
                    if not role:
                        return await interaction.followup.send(
                            f"❌ Không tìm thấy role {ROLE_RECRUIT}.", ephemeral=True
                        )
                    await member.add_roles(role, reason="Duyet don vao LSPD")

                elif kind == "XIN ROI NGANH":
                    role = get_role(guild, ROLE_LSPD)
                    recruit = get_role(guild, ROLE_RECRUIT)
                    roles = [r for r in (role, recruit) if r and r in member.roles]
                    if roles:
                        await member.remove_roles(*roles, reason="Duyet don roi nganh")

                elif kind == "CALLSIGN":
                    parts = data.split("|")
                    if len(parts) >= 3:
                        await member.edit(
                            nick=f"{parts[0].strip()} | {parts[1].strip()} | {parts[2].strip()}",
                            reason="Duyet callsign LSPD"
                        )

            db.execute(
                "UPDATE applications SET status=? WHERE id=?",
                ("approved" if approved else "rejected", app_id)
            )
            db.commit()

            embed.color = discord.Color.green() if approved else discord.Color.red()
            embed.add_field(
                name="Kết quả",
                value="✅ Đã duyệt" if approved else "❌ Đã từ chối"
            )
            await interaction.message.edit(embed=embed, view=None)

            if member:
                try:
                    await member.send(
                        f"Đơn **{kind}** của bạn tại CANYON CITY đã "
                        + ("được duyệt." if approved else "bị từ chối.")
                    )
                except discord.Forbidden:
                    pass

            await interaction.followup.send(
                "✅ Đã duyệt đơn." if approved else "❌ Đã từ chối đơn.",
                ephemeral=True
            )

        except Exception as e:
            print(f"LOI XU LY DON: {type(e).__name__}: {e}")
            await interaction.followup.send(
                f"❌ Không xử lý được đơn: {type(e).__name__}: {e}",
                ephemeral=True
            )

    @discord.ui.button(label="Duyệt", emoji="✅", style=discord.ButtonStyle.success,
                       custom_id="canyon:approve")
    async def approve(self, interaction, button):
        await self.decide(interaction, True)

    @discord.ui.button(label="Từ chối", emoji="❌", style=discord.ButtonStyle.danger,
                       custom_id="canyon:reject")
    async def reject(self, interaction, button):
        await self.decide(interaction, False)


class ApplyModal(discord.ui.Modal, title="Đăng ký vào ngành PD"):
    ic = discord.ui.TextInput(label="Tên nhân vật IC", max_length=50)
    age = discord.ui.TextInput(label="Tuổi IC", max_length=10)
    experience = discord.ui.TextInput(label="Kinh nghiệm cảnh sát", max_length=300)
    reason = discord.ui.TextInput(label="Lý do muốn vào ngành", style=discord.TextStyle.paragraph, max_length=500)
    activity = discord.ui.TextInput(label="Thời gian hoạt động mỗi ngày", max_length=100)

    async def on_submit(self, interaction):
        data = (
            f"Tên IC: {self.ic.value}\nTuổi IC: {self.age.value}\n"
            f"Kinh nghiệm: {self.experience.value}\nLý do: {self.reason.value}\n"
            f"Hoạt động: {self.activity.value}"
        )
        app_id = add_app(interaction.user.id, "DANG KY NGANH", data)
        ok = await send_review(interaction.guild, app_id, interaction.user.id,
                               "DANG KY NGANH", data)
        await interaction.response.send_message(
            "✅ Đã gửi đơn." if ok else
            f"⚠️ Đã lưu đơn số {app_id}, nhưng chưa gửi được. Hãy tạo phòng #{REVIEW_CHANNEL}.",
            ephemeral=True
        )


class LeaveModal(discord.ui.Modal, title="Đơn xin nghỉ phép"):
    ic = discord.ui.TextInput(label="Tên nhân vật IC", max_length=50)
    callsign = discord.ui.TextInput(label="Callsign hiện tại", max_length=10)
    rank = discord.ui.TextInput(label="Chức vụ", max_length=50)
    dates = discord.ui.TextInput(label="Thời gian nghỉ từ ngày đến ngày", max_length=100)
    reason = discord.ui.TextInput(label="Lý do xin nghỉ", style=discord.TextStyle.paragraph, max_length=500)

    async def on_submit(self, interaction):
        data = (
            f"Tên IC: {self.ic.value}\nCallsign: {self.callsign.value}\n"
            f"Chức vụ: {self.rank.value}\nThời gian: {self.dates.value}\n"
            f"Lý do: {self.reason.value}"
        )
        app_id = add_app(interaction.user.id, "NGHI PHEP", data)
        ok = await send_review(interaction.guild, app_id, interaction.user.id,
                               "NGHI PHEP", data)
        await interaction.response.send_message(
            "✅ Đã gửi đơn." if ok else
            f"⚠️ Đã lưu đơn số {app_id}, hãy tạo phòng #{REVIEW_CHANNEL}.",
            ephemeral=True
        )


class ResignModal(discord.ui.Modal, title="Đơn xin rời ngành"):
    ic = discord.ui.TextInput(label="Tên nhân vật IC", max_length=50)
    callsign = discord.ui.TextInput(label="Callsign hiện tại", max_length=10)
    rank = discord.ui.TextInput(label="Chức vụ hiện tại", max_length=50)
    reason = discord.ui.TextInput(label="Lý do rời ngành", style=discord.TextStyle.paragraph, max_length=500)
    equipment = discord.ui.TextInput(label="Đã bàn giao tài sản chưa?", max_length=200)

    async def on_submit(self, interaction):
        data = (
            f"Tên IC: {self.ic.value}\nCallsign: {self.callsign.value}\n"
            f"Chức vụ: {self.rank.value}\nLý do: {self.reason.value}\n"
            f"Bàn giao: {self.equipment.value}"
        )
        app_id = add_app(interaction.user.id, "XIN ROI NGANH", data)
        ok = await send_review(interaction.guild, app_id, interaction.user.id,
                               "XIN ROI NGANH", data)
        await interaction.response.send_message(
            "✅ Đã gửi đơn." if ok else
            f"⚠️ Đã lưu đơn số {app_id}, hãy tạo phòng #{REVIEW_CHANNEL}.",
            ephemeral=True
        )


class CallsignModal(discord.ui.Modal, title="Đăng ký Callsign LSPD"):
    number = discord.ui.TextInput(label="Callsign từ 500 đến 799", max_length=3)
    rank = discord.ui.TextInput(label="Chức vụ", max_length=50)
    name = discord.ui.TextInput(label="Tên nhân vật IC", max_length=50)

    async def on_submit(self, interaction):
        try:
            number = int(self.number.value)
        except ValueError:
            return await interaction.response.send_message(
                "❌ Callsign phải là số từ 500 đến 799.", ephemeral=True
            )

        if not 500 <= number <= 799:
            return await interaction.response.send_message(
                "❌ Callsign phải nằm trong khoảng 500–799.", ephemeral=True
            )

        used = db.execute(
            "SELECT id FROM applications WHERE callsign=? AND status!='rejected'",
            (number,)
        ).fetchone()
        if used:
            return await interaction.response.send_message(
                "❌ Callsign này đã được đăng ký hoặc cấp cho người khác.",
                ephemeral=True
            )

        data = f"{number} | {self.rank.value} | {self.name.value}"
        app_id = add_app(interaction.user.id, "CALLSIGN", data, number)
        ok = await send_review(interaction.guild, app_id, interaction.user.id,
                               "CALLSIGN", data)
        await interaction.response.send_message(
            "✅ Đã gửi đơn Callsign." if ok else
            f"⚠️ Đã lưu đơn số {app_id}, hãy tạo phòng #{REVIEW_CHANNEL}.",
            ephemeral=True
        )


class RecruitmentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Đăng ký vào ngành", emoji="📝",
                       style=discord.ButtonStyle.primary, custom_id="canyon:apply")
    async def apply(self, interaction, button):
        await interaction.response.send_modal(ApplyModal())


class LeaveView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Xin nghỉ phép", emoji="📅",
                       style=discord.ButtonStyle.primary, custom_id="canyon:leave")
    async def leave(self, interaction, button):
        await interaction.response.send_modal(LeaveModal())


class ResignView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Xin rời ngành", emoji="🚪",
                       style=discord.ButtonStyle.danger, custom_id="canyon:resign")
    async def resign(self, interaction, button):
        await interaction.response.send_modal(ResignModal())


class CallsignView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Đăng ký Callsign", emoji="🪪",
                       style=discord.ButtonStyle.primary, custom_id="canyon:callsign")
    async def callsign(self, interaction, button):
        await interaction.response.send_modal(CallsignModal())


class DutyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def set_duty(self, interaction, status):
        db.execute(
            "INSERT INTO duty(user_id,status) VALUES(?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET status=excluded.status",
            (interaction.user.id, status)
        )
        db.commit()
        await interaction.response.send_message(
            f"Trạng thái của bạn: **{status}**.", ephemeral=True
        )

    @discord.ui.button(label="On Duty", emoji="🟢",
                       style=discord.ButtonStyle.success, custom_id="canyon:on")
    async def on_duty(self, interaction, button):
        await self.set_duty(interaction, "On Duty")

    @discord.ui.button(label="Off Duty", emoji="🔴",
                       style=discord.ButtonStyle.danger, custom_id="canyon:off")
    async def off_duty(self, interaction, button):
        await self.set_duty(interaction, "Off Duty")


class PersonnelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Xem nhân sự", emoji="👮",
                       style=discord.ButtonStyle.primary, custom_id="canyon:staff")
    async def staff(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            rows = db.execute(
                "SELECT user_id,status FROM duty ORDER BY user_id"
            ).fetchall()
            lines = []
            for uid, status in rows:
                member = interaction.guild.get_member(uid)
                if member:
                    lines.append(f"{member.mention} — {status}")
            msg = "\n".join(lines) or "Chưa có dữ liệu trực ban."
            await interaction.followup.send(msg[:1900], ephemeral=True)
        except Exception as e:
            print("Loi nut Xem nhan su:", repr(e))
            await interaction.followup.send(
                "Có lỗi khi tải nhân sự. Hãy xem Termux.",
                ephemeral=True
            )



LSPD_ROLE_NAMES = [
    "Chief of Police",
    "Assistant Chief",
    "Deputy Commissioner",
    "HIGH HIGH COMMAND",
    "Commander",
    "Captain",
    "HIGH COMMAND",
    "Lieutenant",
    "Sergeant",
    "Corporal",
    "Senior Officer",
    "Police Officer",
    "Cadet",
    "L.S.P.D",
]

db.execute("""
CREATE TABLE IF NOT EXISTS lspd_roster_board (
    guild_id INTEGER PRIMARY KEY,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL
)
""")
db.commit()


async def lspd_roster_embed(guild):
    embed = discord.Embed(
        title="🚔 LOS SANTOS POLICE DEPARTMENT",
        description="📋 **BẢNG THỐNG KÊ NHÂN SỰ**\n🔄 Tự cập nhật theo role Discord",
        color=discord.Color.dark_blue()
    )

    for role_name in LSPD_ROLE_NAMES:
        role = discord.utils.get(guild.roles, name=role_name)
        if role is None:
            value = "⚠️ Chưa tìm thấy role"
        else:
            members = sorted(role.members, key=lambda m: m.display_name.lower())
            value = "\n".join(m.mention for m in members) if members else "Trống"

        embed.add_field(name=f"🎖️ {role_name}", value=value[:1024], inline=False)

    embed.set_footer(text="LSPD • Bảng nhân sự")
    return embed


@bot.tree.command(
    name="tao-bang-nhansu-lspd",
    description="Tạo bảng thống kê nhân sự LSPD"
)
@app_commands.checks.has_permissions(manage_guild=True)
async def tao_bang_nhansu_lspd(interaction: discord.Interaction):
    if not interaction.guild or not interaction.channel:
        await interaction.response.send_message(
            "Lệnh này chỉ dùng trong server.", ephemeral=True
        )
        return

    embed = await lspd_roster_embed(interaction.guild)
    await interaction.response.send_message(
        "Đang tạo bảng thống kê...", ephemeral=True
    )
    message = await interaction.channel.send(embed=embed)
    db.execute(
        "INSERT INTO lspd_roster_board(guild_id, channel_id, message_id) "
        "VALUES(?, ?, ?) ON CONFLICT(guild_id) DO UPDATE SET "
        "channel_id=excluded.channel_id, message_id=excluded.message_id",
        (interaction.guild.id, interaction.channel.id, message.id)
    )
    db.commit()
    await interaction.followup.send(
        "✅ Đã lưu bảng nhân sự. Bot sẽ cập nhật chính tin nhắn này khi role thay đổi.",
        ephemeral=True
    )


@bot.event
async def on_member_update(before, after):
    if before.roles == after.roles:
        return

    try:
        row = db.execute(
            "SELECT channel_id, message_id FROM lspd_roster_board WHERE guild_id=?",
            (after.guild.id,)
        ).fetchone()
        if not row:
            return

        channel_id, message_id = row
        channel = after.guild.get_channel(channel_id)
        if channel is None:
            return

        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            print("Bang nhan su LSPD khong con ton tai; chua tao bang moi.")
            return

        embed = await lspd_roster_embed(after.guild)
        await message.edit(embed=embed)

    except Exception as e:
        print("Loi cap nhat bang nhan su LSPD:", repr(e))

@bot.event
async def setup_hook():
    bot.add_view(RecruitmentView())
    bot.add_view(LeaveView())
    bot.add_view(ResignView())
    bot.add_view(CallsignView())
    bot.add_view(DutyView())
    bot.add_view(PersonnelView())
    bot.add_view(ReviewView())
    bot.add_view(CaTrucView())
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    else:
        await bot.tree.sync()


@bot.event
async def on_ready():
    print(f"Bot online: {bot.user}")


async def make_board(interaction, title, description, view):
    await interaction.response.defer(ephemeral=True, thinking=True)
    embed = discord.Embed(
        title=title, description=description, color=discord.Color.blue()
    )
    await interaction.channel.send(embed=embed, view=view)
    await interaction.followup.send(
        "✅ Đã tạo bảng trong phòng này.", ephemeral=True
    )

@bot.tree.command(name="tao-bang-dang-ky", description="Tạo bảng xin vào ngành PD/LSPD")
@app_commands.checks.has_permissions(manage_guild=True)
async def board_apply(interaction):
    await make_board(interaction, "🚔 TUYỂN DỤNG LSPD",
                      "Bấm nút bên dưới để điền đơn xin vào ngành.", RecruitmentView())


@bot.tree.command(name="tao-bang-nghiphep", description="Tạo bảng xin nghỉ phép")
@app_commands.checks.has_permissions(manage_guild=True)
async def board_leave(interaction):
    await make_board(interaction, "📅 XIN NGHỈ PHÉP",
                      "Điền đơn xin nghỉ phép để cấp chỉ huy xét duyệt.", LeaveView())


@bot.tree.command(name="tao-bang-xin-roi", description="Tạo bảng xin rời ngành")
@app_commands.checks.has_permissions(manage_guild=True)
async def board_resign(interaction):
    await make_board(interaction, "🚪 XIN RỜI NGÀNH",
                      "Điền đơn xin rời ngành. Chỉ huy sẽ xét duyệt.", ResignView())


@bot.tree.command(name="tao-bang-callsign", description="Tạo bảng đăng ký Callsign")
@app_commands.checks.has_permissions(manage_guild=True)
async def board_callsign(interaction):
    await make_board(interaction, "🪪 ĐĂNG KÝ CALLSIGN",
                      "Callsign hợp lệ: 500–799. Không được trùng số.", CallsignView())


@bot.tree.command(name="tao-bang-duty", description="Tạo bảng On Duty và Off Duty")
@app_commands.checks.has_permissions(manage_guild=True)
async def board_duty(interaction):
    await make_board(interaction, "🚨 TRẠNG THÁI TRỰC BAN",
                      "Chọn trạng thái hiện tại của bạn.", DutyView())


@bot.tree.command(name="tao-bang-nhansu", description="Tạo bảng nhân sự LSPD")
@app_commands.checks.has_permissions(manage_guild=True)
async def board_personnel(interaction):
    await make_board(interaction, "👮 NHÂN SỰ LSPD",
                      "Bấm nút để xem trạng thái trực ban đã ghi nhận.", PersonnelView())


@bot.tree.command(name="kiemtra-bot", description="Kiểm tra bot")
async def check_bot(interaction):
    await interaction.response.send_message(
        f"✅ Bot đang hoạt động. Ping: {round(bot.latency * 1000)} ms",
        ephemeral=True
    )


@bot.tree.command(name="kiemtra-nhansu", description="Xem trạng thái trực ban")
async def check_staff(interaction):
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        rows = db.execute(
            "SELECT user_id, started FROM duty ORDER BY user_id"
        ).fetchall()

        lines = []
        for uid, started in rows:
            member = interaction.guild.get_member(int(uid))
            if member:
                status = "🟢 ĐANG TRỰC" if started else "🔴 CHƯA TRỰC"
                lines.append(f"{member.mention} — {status}")

        msg = "\\n".join(lines) or "Chưa có dữ liệu trực ban."
        await interaction.followup.send(msg[:1900], ephemeral=True)
    except Exception as e:
        print("Loi kiemtra-nhansu:", repr(e))
        await interaction.followup.send(
            "Lỗi đọc nhân sự. Xem Termux để biết chi tiết.",
            ephemeral=True
        )

# ===== DANG KY CA TRUC LSPD =====

class CaTrucModal(discord.ui.Modal, title="Đăng ký ca trực LSPD"):
    ten_ic = discord.ui.TextInput(
        label="Tên IC",
        placeholder="Nhập tên nhân vật",
        max_length=80
    )
    callsign = discord.ui.TextInput(
        label="Callsign của bạn",
        placeholder="Ví dụ: 911",
        max_length=30
    )
    thoi_gian = discord.ui.TextInput(
        label="Thời gian ca trực linh hoạt",
        placeholder="Ví dụ: 19:00 - 21:00",
        max_length=100
    )
    cam_ket = discord.ui.TextInput(
        label="Cam kết",
        placeholder="Cam kết thực hiện đúng thời gian đã đăng ký",
        style=discord.TextStyle.paragraph,
        max_length=300
    )

    async def on_submit(self, interaction: discord.Interaction):
        channel = discord.utils.get(
            interaction.guild.text_channels,
            name="cam-ket-ca-truc"
        )

        if channel is None:
            return await interaction.response.send_message(
                "❌ Không tìm thấy room #cam-ket-ca-truc. "
                "Hãy kiểm tra tên room.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="📋 ĐĂNG KÝ CA TRỰC LSPD",
            color=discord.Color.blue()
        )
        embed.add_field(name="👤 Tên IC", value=self.ten_ic.value, inline=False)
        embed.add_field(name="📻 Callsign", value=self.callsign.value, inline=False)
        embed.add_field(
            name="🕒 Thời gian ca trực",
            value=self.thoi_gian.value,
            inline=False
        )
        embed.add_field(
            name="📜 Cam kết",
            value=self.cam_ket.value,
            inline=False
        )
        embed.add_field(
            name="👮 Người đăng ký",
            value=interaction.user.mention,
            inline=False
        )
        embed.set_footer(text="Ca trực được ghi nhận để cấp cao theo dõi • Không cần duyệt")

        try:
            await channel.send(embed=embed)
            await interaction.response.send_message(
                "✅ Đã gửi đăng ký ca trực vào #cam-ket-ca-truc!",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Bot thiếu quyền gửi tin nhắn hoặc nhúng liên kết "
                "trong room ca trực.",
                ephemeral=True
            )


class CaTrucView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="📋 Đăng ký ca trực",
        style=discord.ButtonStyle.primary,
        custom_id="lspd_dang_ky_ca_truc"
    )
    async def dang_ky(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.send_modal(CaTrucModal())


@bot.tree.command(
    name="tao-bang-catruc",
    description="Tạo bảng đăng ký ca trực LSPD"
)
async def tao_bang_catruc(interaction: discord.Interaction):
    await interaction.response.send_message(
        "📋 **ĐĂNG KÝ CA TRỰC LSPD**\n"
        "Vui lòng bấm nút bên dưới và điền đầy đủ thông tin.\n"
        "Đăng ký không cần duyệt; cấp cao sẽ theo dõi ca trực.",
        view=CaTrucView()
    )




@bot.tree.command(
    name="xem-role-lspd",
    description="Liệt kê tên tất cả role trong server"
)
async def xem_role_lspd(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message(
            "Lệnh này chỉ dùng trong server Discord.",
            ephemeral=True
        )
        return

    roles = sorted(
        [r for r in interaction.guild.roles
         if r != interaction.guild.default_role],
        key=lambda r: r.position,
        reverse=True
    )

    lines = [f"🎖️ {r.name}" for r in roles]
    chunks = []
    current = "🚔 **DANH SÁCH ROLE LSPD**\n\n"

    for line in lines:
        if len(current) + len(line) + 1 > 1800:
            chunks.append(current)
            current = ""
        current += line + "\n"

    if current:
        chunks.append(current)

    await interaction.response.send_message(
        chunks[0], ephemeral=True
    )
    for chunk in chunks[1:]:
        await interaction.followup.send(
            chunk, ephemeral=True
        )


WELCOME_CHANNEL_ID = 1553066506131079210  # Thay bằng ID phòng Welcome

@bot.event
async def on_member_join(member):
    channel = member.guild.get_channel(WELCOME_CHANNEL_ID)

    if channel is None:
        return

    import os

    embed = discord.Embed(
        title="🚔 WELCOME TO LSPD",
        description=(
            f"Chào mừng {member.mention} đến với "
            "**LOS SANTOS POLICE DEPARTMENT**!\n\n"
            "📋 Đọc nội quy ngành.\n"
            "🎖️ Hoàn tất thủ tục nhận role.\n"
            "🚨 Chúc bạn hoàn thành tốt nhiệm vụ!"
        ),
        color=0x1877F2
    )

    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_footer(
        text=f"LSPD • Thành viên thứ {member.guild.member_count}"
    )

    image_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "welcome_lspd.jpg."
    )

    if os.path.isfile(image_path):
        file = discord.File(image_path, filename="welcome_lspd.png")
        embed.set_image(url="attachment://welcome_lspd.png")
        await channel.send(
            content=f"🚔 Chào mừng {member.mention}!",
            embed=embed,
            file=file
        )
    else:
        await channel.send(
            content=f"🚔 Chào mừng {member.mention}!",
            embed=embed
        )
bot.run(TOKEN)






bot.run(TOKEN)










