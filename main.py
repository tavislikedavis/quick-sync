# title: Quick Sync?
# desc: A boss-fight shmup. Ship your code while your manager tries to "quickly sync".
# controls: arrows/WASD move, Z/Space (hold) fire, X do-not-disturb, Enter start, Q quit

import math

import pyxel

W, H = 200, 200

SCENE_TITLE, SCENE_PLAY, SCENE_WIN, SCENE_LOSE = range(4)

PLAYER_SPEED = 2
PLAYER_FOCUS = 5
PLAYER_DND = 3
FIRE_INTERVAL = 4
SHOT_SPEED = 5
INVULN_FRAMES = 75

BOSS_HP = 360
BOSS_Y = 30

PING_TEXTS = ["hey", "ping", "?", "u there?", "+1", "hi!!", "yo"]
SYNC_TEXTS = [
    "quick sync?",
    "quick huddle",
    "got a sec?",
    "hop on a call?",
    "circling back",
    "any updates?",
    "5 min?",
    "jump on zoom?",
]
INVITE_TEXTS = ["Quick Chat", "Sync", "Touch Base", "Alignment", "1:1", "Standup 2", "Pre-mtg"]
BIG_CHAT_SHORT = "Can we chat?"
BIG_CHAT_FULL = "Can we chat? it won't take long"
RAGE_TEXTS = ["per my last message", "just bumping this", "URGENT", "??", "following up"]
PHASE_LINES = [
    "hey! got a sec?",
    "I'll just throw something on your cal",
    "Can we chat? it won't take long",
    "per my last message...",
]
HIT_QUIPS = ["ok sure", "uh, yeah?", "joining...", "sure, 5 min", "brb", "on mute"]
WIN_LINE = "ok let's take this offline"
LOSE_LINE = "It did, in fact, take long."

# Image bank 0 layout
SPR_MANAGER = (0, 0)
SPR_DEV = (16, 0)
SPR_COFFEE = (32, 0)

bullets = []  # interruptions (enemy projectiles)
shots = []  # player projectiles
effects = []  # floating text, sparks, rings
pickups = []


def overlaps(a, b):
    return a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h


def cleanup(entities):
    entities[:] = [e for e in entities if e.is_alive]


def text_w(s):
    return len(s) * 4


def center_text(y, s, col):
    pyxel.text((W - text_w(s)) // 2, y, s, col)


def shadow_text(x, y, s, col, shadow=1):
    pyxel.text(x + 1, y + 1, s, shadow)
    pyxel.text(x, y, s, col)


def big_text(cx, y, s, col, scale):
    """Draw scaled text by rendering into image bank 1 and blitting it."""
    img = pyxel.images[1]
    w = text_w(s)
    img.rect(0, 0, w, 6, 0)
    img.text(0, 0, s, col)
    # blt scales around the region's center, so position by center
    pyxel.blt(cx - w / 2, y, 1, 0, 0, w, 6, 0, scale=scale)


class Box:
    """Simple AABB holder for collision tests."""

    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h


# ---------------------------------------------------------------------------
# Interruptions
# ---------------------------------------------------------------------------


class Badge:
    """A red notification dot. Small, fast, comes in spreads."""

    def __init__(self, x, y, angle, speed):
        self.x, self.y = x, y
        self.vx = math.cos(math.radians(angle)) * speed
        self.vy = math.sin(math.radians(angle)) * speed
        self.w = self.h = 5
        self.is_alive = True
        bullets.append(self)

    def hitbox(self):
        return Box(self.x - 1.5, self.y - 1.5, 3, 3)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        if not (-10 < self.x < W + 10 and -10 < self.y < H + 10):
            self.is_alive = False
            App.stats["dodged"] += 1

    def draw(self):
        pyxel.circ(self.x, self.y, 2.5, 8)
        pyxel.pset(self.x, self.y - 1, 7)
        pyxel.pset(self.x, self.y + 1, 7)


class Bubble:
    """A chat message. Text is the projectile."""

    STYLES = {
        "chat": (7, 1, 13),  # bg, fg, border
        "ping": (6, 1, 12),
        "invite": (12, 7, 1),
        "big": (10, 1, 9),
        "rage": (8, 7, 2),
    }

    def __init__(
        self,
        x,
        y,
        text,
        vx=0.0,
        vy=1.0,
        style="chat",
        homing=0.0,
        wobble=0.0,
        life=None,
        grow_to=None,
    ):
        self.x, self.y = x, y  # center
        self.text = text
        self.vx, self.vy = vx, vy
        self.style = style
        self.homing = homing
        self.wobble = wobble
        self.life = life
        self.grow_to = grow_to
        self.age = 0
        self.is_alive = True
        self.resize()
        bullets.append(self)

    def resize(self):
        self.w = text_w(self.text) + 5
        self.h = 9

    def hitbox(self):
        # Slightly forgiving: shrink by 2px on each side
        return Box(self.x - self.w / 2 + 2, self.y - self.h / 2 + 2, self.w - 4, self.h - 4)

    def update(self):
        self.age += 1

        if self.grow_to and self.age == 45:
            self.text = self.grow_to
            self.grow_to = None
            self.resize()

        if self.homing:
            target = App.instance.player
            dx = target.x - self.x
            dy = target.y - self.y
            d = math.hypot(dx, dy) or 1
            speed = math.hypot(self.vx, self.vy) or 0.6
            self.vx += (dx / d * speed - self.vx) * self.homing
            self.vy += (dy / d * speed - self.vy) * self.homing

        self.x += self.vx + (math.sin(self.age * 0.12) * self.wobble)
        self.y += self.vy
        if self.homing:
            # Homing bubbles stay fully on screen so they're always readable
            self.x = pyxel.clamp(self.x, self.w / 2 + 1, W - self.w / 2 - 1)

        if self.life is not None:
            self.life -= 1
            if self.life <= 0:
                self.is_alive = False
                FloatText(self.x, self.y, "(45 min later)", 13)
                return

        margin = self.w
        if not (-margin < self.x < W + margin and -20 < self.y < H + 20):
            self.is_alive = False
            App.stats["dodged"] += 1

    def draw(self):
        bg, fg, border = self.STYLES[self.style]
        x = self.x - self.w / 2
        y = self.y - self.h / 2
        if self.style == "invite":
            # Calendar event block: colored bar on the left
            pyxel.rect(x, y, self.w, self.h, bg)
            pyxel.rect(x, y, 2, self.h, border)
            pyxel.text(x + 3, y + 2, self.text, fg)
            return
        pyxel.rect(x + 1, y, self.w - 2, self.h, bg)
        pyxel.rect(x, y + 1, self.w, self.h - 2, bg)
        pyxel.rectb(x + 1, y, self.w - 2, 1, border)
        pyxel.rectb(x + 1, y + self.h - 1, self.w - 2, 1, border)
        pyxel.line(x, y + 1, x, y + self.h - 2, border)
        pyxel.line(x + self.w - 1, y + 1, x + self.w - 1, y + self.h - 2, border)
        # Speech tail
        pyxel.tri(x + 3, y + self.h - 1, x + 7, y + self.h - 1, x + 3, y + self.h + 2, bg)
        pyxel.text(x + 3, y + 2, self.text, fg)


# ---------------------------------------------------------------------------
# Effects & pickups
# ---------------------------------------------------------------------------


class FloatText:
    def __init__(self, x, y, text, col, life=40):
        self.x, self.y = x - text_w(text) / 2, y
        self.text, self.col, self.life = text, col, life
        self.is_alive = True
        effects.append(self)

    def update(self):
        self.y -= 0.5
        self.life -= 1
        self.is_alive = self.life > 0

    def draw(self):
        shadow_text(self.x, self.y, self.text, self.col)


class Spark:
    def __init__(self, x, y, col=10):
        self.x, self.y, self.col = x, y, col
        self.r = 1
        self.is_alive = True
        effects.append(self)

    def update(self):
        self.r += 1
        self.is_alive = self.r < 5

    def draw(self):
        pyxel.circb(self.x, self.y, self.r, self.col)


class Ring:
    """Do-not-disturb shockwave."""

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.r = 4
        self.is_alive = True
        effects.append(self)

    def update(self):
        self.r += 7
        self.is_alive = self.r < 300

    def draw(self):
        pyxel.circb(self.x, self.y, self.r, 11)
        pyxel.circb(self.x, self.y, self.r - 3, 3)


class Coffee:
    def __init__(self, x):
        self.x, self.y = x, -8
        self.w = self.h = 8
        self.is_alive = True
        pickups.append(self)

    def update(self):
        self.y += 0.8
        self.x += math.sin(pyxel.frame_count * 0.08) * 0.4
        if self.y > H:
            self.is_alive = False

    def draw(self):
        pyxel.blt(self.x, self.y, 0, *SPR_COFFEE, 8, 8, 0)


# ---------------------------------------------------------------------------
# Player & Boss
# ---------------------------------------------------------------------------


class Player:
    def __init__(self):
        self.x, self.y = W / 2, H - 30  # center
        self.focus = PLAYER_FOCUS
        self.dnd = PLAYER_DND
        self.invuln = 0
        self.fire_cd = 0
        self.status_timer = 0

    def hitbox(self):
        # Tiny bullet-hell hitbox around the dev's head
        return Box(self.x - 2, self.y - 2, 4, 4)

    def body(self):
        return Box(self.x - 7, self.y - 7, 14, 14)

    def update(self):
        dx = (btn_any(pyxel.KEY_RIGHT, pyxel.KEY_D, pyxel.GAMEPAD1_BUTTON_DPAD_RIGHT)) - (
            btn_any(pyxel.KEY_LEFT, pyxel.KEY_A, pyxel.GAMEPAD1_BUTTON_DPAD_LEFT)
        )
        dy = (btn_any(pyxel.KEY_DOWN, pyxel.KEY_S, pyxel.GAMEPAD1_BUTTON_DPAD_DOWN)) - (
            btn_any(pyxel.KEY_UP, pyxel.KEY_W, pyxel.GAMEPAD1_BUTTON_DPAD_UP)
        )
        speed = PLAYER_SPEED * (0.7071 if dx and dy else 1)
        # Hold shift to move precisely
        if pyxel.btn(pyxel.KEY_SHIFT) or pyxel.btn(pyxel.GAMEPAD1_BUTTON_B):
            speed *= 0.5
        self.x = pyxel.clamp(self.x + dx * speed, 8, W - 8)
        self.y = pyxel.clamp(self.y + dy * speed, 60, H - 18)

        self.fire_cd -= 1
        if btn_any(pyxel.KEY_Z, pyxel.KEY_SPACE, pyxel.GAMEPAD1_BUTTON_A) and self.fire_cd <= 0:
            self.fire_cd = FIRE_INTERVAL
            Shot(self.x - 4, self.y - 8)
            Shot(self.x + 2, self.y - 8)
            pyxel.play(3, 0)

        if btnp_any(pyxel.KEY_X, pyxel.GAMEPAD1_BUTTON_X) and self.dnd > 0:
            self.dnd -= 1
            self.do_not_disturb()

        if self.invuln > 0:
            self.invuln -= 1
        if self.status_timer > 0:
            self.status_timer -= 1

    def do_not_disturb(self):
        Ring(self.x, self.y)
        declined = 0
        for b in bullets:
            if declined < 6 and isinstance(b, Bubble):
                FloatText(b.x, b.y, "declined", 11, 30)
                declined += 1
            b.is_alive = False
        App.stats["declined"] += len(bullets)
        self.invuln = max(self.invuln, 45)
        App.instance.boss.stun = 75
        App.instance.banner("DO NOT DISTURB", 11, 50)
        pyxel.play(3, 4)

    def hit(self):
        if self.invuln > 0:
            return
        self.focus -= 1
        self.invuln = INVULN_FRAMES
        self.status_timer = INVULN_FRAMES
        App.stats["meetings"] += 1
        FloatText(self.x, self.y - 12, HIT_QUIPS[pyxel.rndi(0, len(HIT_QUIPS) - 1)], 10)
        # Clear nearby interruptions so a hit doesn't chain
        for b in bullets:
            if math.hypot(b.x - self.x, b.y - self.y) < 40:
                b.is_alive = False
        App.instance.shake = 8
        pyxel.play(3, 2)

    def draw(self):
        if self.invuln > 0 and pyxel.frame_count % 4 < 2:
            return
        pyxel.blt(self.x - 8, self.y - 8, 0, *SPR_DEV, 16, 16, 0)
        # Focus mode glow on the headphones when DND is available
        if pyxel.btn(pyxel.KEY_SHIFT):
            pyxel.circb(self.x, self.y, 2, 7)


class Shot:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.w, self.h = 2, 6
        self.is_alive = True
        shots.append(self)

    def update(self):
        self.y -= SHOT_SPEED
        if self.y < -8:
            self.is_alive = False

    def draw(self):
        pyxel.rect(self.x, self.y, self.w, self.h, 11)
        pyxel.pset(self.x, self.y, 7)


class Boss:
    def __init__(self):
        self.x, self.y = W / 2, BOSS_Y  # center
        self.hp = BOSS_HP
        self.t = 0
        self.flash = 0
        self.stun = 0
        self.phase = 0
        self.big_chat = None

    def box(self):
        return Box(self.x - 9, self.y - 9, 18, 18)

    def phase_for_hp(self):
        r = self.hp / BOSS_HP
        if r > 0.75:
            return 1
        if r > 0.5:
            return 2
        if r > 0.25:
            return 3
        return 4

    def aim(self, tx, ty):
        return math.degrees(math.atan2(ty - self.y, tx - self.x))

    def update(self, player):
        self.t += 1
        if self.flash > 0:
            self.flash -= 1

        p = self.phase_for_hp()
        if p != self.phase:
            self.phase = p
            App.instance.toast(PHASE_LINES[p - 1])
            if p > 1:
                pyxel.play(3, 1)

        speed = 1.0 + (p - 1) * 0.25
        self.x = W / 2 + math.sin(self.t * 0.02 * speed) * 62
        self.y = BOSS_Y + math.sin(self.t * 0.05) * 5

        if self.stun > 0:
            self.stun -= 1
            return
        if self.t < 60:
            return  # grace period

        f = self.t
        aim = self.aim(player.x, player.y)

        # Phase 1+: notification badge spreads
        badge_every = [0, 42, 34, 28, 22][p]
        if f % badge_every == 0:
            n = 3 + p
            spread = 14 + p * 4
            for i in range(n):
                a = aim - spread + (2 * spread) * i / (n - 1)
                Badge(self.x, self.y + 8, a, 1.5 + p * 0.15)

        # Phase 1+: chat bubbles
        chat_every = [0, 75, 62, 55, 45][p]
        if f % chat_every == 0:
            text = SYNC_TEXTS[pyxel.rndi(0, len(SYNC_TEXTS) - 1)]
            a = math.radians(aim + pyxel.rndf(-15, 15))
            spd = 0.9 + p * 0.1
            Bubble(self.x, self.y + 12, text, math.cos(a) * spd, math.sin(a) * spd, wobble=0.4)

        # Phase 1+: short text pings rained from random spots
        if f % [0, 50, 45, 40, 32][p] == 25:
            text = PING_TEXTS[pyxel.rndi(0, len(PING_TEXTS) - 1)]
            Bubble(pyxel.rndf(20, W - 20), -6, text, 0, 1.1 + p * 0.1, style="ping")

        # Phase 2+: calendar invite walls with a gap
        if p >= 2 and f % [0, 0, 210, 180, 150][p] == 100:
            self.invite_wall()

        # Phase 3+: the big one, which homes in slowly and expands
        if p >= 3 and (self.big_chat is None or not self.big_chat.is_alive) and f % 120 == 0:
            self.big_chat = Bubble(
                self.x,
                self.y + 14,
                BIG_CHAT_SHORT,
                0,
                0.6,
                style="big",
                homing=0.03,
                life=330,
                grow_to=BIG_CHAT_FULL,
            )
            pyxel.play(3, 1)

        # Phase 4: rage follow-ups, fast and aimed
        if p >= 4 and f % 38 == 0:
            text = RAGE_TEXTS[pyxel.rndi(0, len(RAGE_TEXTS) - 1)]
            a = math.radians(aim)
            Bubble(self.x, self.y + 12, text, math.cos(a) * 2.1, math.sin(a) * 2.1, style="rage")

    def invite_wall(self):
        seg_w = 48
        gap_w = 40
        gap_x = pyxel.rndi(10, W - gap_w - 10)
        x = -4
        while x < W:
            if x + seg_w > gap_x and x < gap_x + gap_w:
                x = gap_x + gap_w
                continue
            label = INVITE_TEXTS[pyxel.rndi(0, len(INVITE_TEXTS) - 1)]
            label = label[: (seg_w - 6) // 4]
            b = Bubble(x + seg_w / 2, -8, label, 0, 0.9, style="invite")
            b.w = seg_w - 2
            x += seg_w

    def hit(self):
        self.hp -= 1
        self.flash = 3
        App.stats["loc"] += 10
        if pyxel.frame_count % 3 == 0:
            pyxel.play(2, 3)

    def draw(self):
        if self.flash > 0:
            for c in range(16):
                pyxel.pal(c, 7)
        pyxel.blt(self.x - 12, self.y - 12, 0, *SPR_MANAGER, 16, 16, 0, scale=1.5)
        pyxel.pal()
        if self.stun > 0 and pyxel.frame_count % 20 < 14:
            shadow_text(self.x - 14, self.y - 22, "...hello?", 13)


def btn_any(*keys):
    return any(pyxel.btn(k) for k in keys)


def btnp_any(*keys):
    return any(pyxel.btnp(k) for k in keys)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


class App:
    instance = None
    stats = {}

    def __init__(self):
        App.instance = self
        pyxel.init(W, H, title="Quick Sync?", fps=60)
        self.init_image()
        self.init_sound()
        self.scene = SCENE_TITLE
        self.reset()
        self.play_music(0)
        pyxel.run(self.update, self.draw)

    def reset(self):
        bullets.clear()
        shots.clear()
        effects.clear()
        pickups.clear()
        App.stats = {"loc": 0, "meetings": 0, "dodged": 0, "declined": 0, "frames": 0}
        self.player = Player()
        self.boss = Boss()
        self.shake = 0
        self.toast_text = ""
        self.toast_timer = 0
        self.banner_text = ""
        self.banner_col = 7
        self.banner_timer = 0
        self.end_timer = 0

    def init_image(self):
        img = pyxel.images[0]
        # Manager: glasses, blue shirt, red tie, badge on a lanyard
        img.set(
            *SPR_MANAGER,
            [
                "0000004444000000",
                "0000444444440000",
                "000444ffff444000",
                "0004ffffffff4000",
                "000ff11ff11ff000",
                "000ffffffffff000",
                "000ffff88ffff000",
                "0000ffffffff0000",
                "00000ffffff00000",
                "000ccc7887ccc000",
                "00ccccc88ccccc00",
                "0fccccc88cccccf0",
                "0fccccc88ccccdf0",
                "0fccccc77ccccdf0",
                "0005555555555000",
                "0005550000555000",
            ],
        )
        # Developer from behind: laptop, headphones, hoodie
        img.set(
            *SPR_DEV,
            [
                "0000000000000000",
                "000dddddddddd000",
                "000d66666666d000",
                "000d63b36b36d000",
                "000d66666666d000",
                "000dddddddddd000",
                "0000008888000000",
                "0000081111800000",
                "0000881111880000",
                "0000081111800000",
                "0002222222222000",
                "0022222222222200",
                "0f222222222222f0",
                "0022222222222200",
                "0002222222222000",
                "0000000000000000",
            ],
        )
        img.set(
            *SPR_COFFEE,
            [
                "00707000",
                "00070700",
                "77777700",
                "74444770",
                "74444707",
                "74444770",
                "77777700",
                "00000000",
            ],
        )

    def init_sound(self):
        s = pyxel.sounds
        s[0].set("c4a3", "p", "2", "f", 2)  # shot
        s[1].set("e3c3r e3c3", "t", "6", "n", 6)  # chat knock
        s[2].set("c2g1c1", "n", "765", "f", 8)  # pulled into meeting
        s[3].set("c4", "n", "2", "f", 2)  # boss hit tick
        s[4].set("c1c2c3c4e4g4c4", "s", "7776554", "n", 4)  # do not disturb
        s[5].set("c3e3g3c4", "p", "6", "n", 4)  # coffee
        s[6].set("c3e3g3c4r g3c4", "s", "6", "n", 12)  # shipped
        s[7].set("g2f2e2d2c2", "t", "6", "f", 16)  # game over
        self.bgm = {
            0: pyxel.gen_bgm(1, 0, 0, 7),  # title
            1: pyxel.gen_bgm(6, 0, 0, 3),  # battle
        }

    def play_music(self, key):
        for ch, mml in enumerate(self.bgm[key][:3]):
            pyxel.play(ch, mml, loop=True)

    def toast(self, text):
        self.toast_text = text
        self.toast_timer = 150

    def banner(self, text, col, frames):
        self.banner_text = text
        self.banner_col = col
        self.banner_timer = frames

    # --- update ------------------------------------------------------------

    def update(self):
        if pyxel.btnp(pyxel.KEY_Q):
            pyxel.quit()

        if self.scene == SCENE_TITLE:
            if btnp_any(pyxel.KEY_RETURN, pyxel.GAMEPAD1_BUTTON_START):
                self.reset()
                self.scene = SCENE_PLAY
                self.play_music(1)
        elif self.scene == SCENE_PLAY:
            self.update_play()
        else:
            self.end_timer += 1
            for group in (bullets, effects):
                for e in group:
                    e.update()
                cleanup(group)
            if self.end_timer > 60 and btnp_any(pyxel.KEY_RETURN, pyxel.GAMEPAD1_BUTTON_START):
                self.scene = SCENE_TITLE
                self.play_music(0)

    def update_play(self):
        App.stats["frames"] += 1
        player, boss = self.player, self.boss
        player.update()
        boss.update(player)

        for group in (bullets, shots, effects, pickups):
            for e in group:
                e.update()

        # Coffee break every ~12 seconds
        if pyxel.frame_count % 720 == 360:
            Coffee(pyxel.rndi(20, W - 28))

        # Shots vs boss
        bbox = boss.box()
        for s in shots:
            if overlaps(s, bbox):
                s.is_alive = False
                boss.hit()
                if pyxel.rndi(0, 3) == 0:
                    Spark(s.x, s.y)

        # Interruptions vs player
        hb = player.hitbox()
        for b in bullets:
            if b.is_alive and overlaps(b.hitbox(), hb):
                b.is_alive = False
                player.hit()

        # Coffee pickup
        body = player.body()
        for c in pickups:
            if overlaps(c, body):
                c.is_alive = False
                if player.focus < PLAYER_FOCUS:
                    player.focus += 1
                    FloatText(c.x + 4, c.y, "+1 FOCUS", 11)
                else:
                    App.stats["loc"] += 500
                    FloatText(c.x + 4, c.y, "+500 LOC", 10)
                pyxel.play(3, 5)

        for group in (bullets, shots, effects, pickups):
            cleanup(group)

        if self.toast_timer > 0:
            self.toast_timer -= 1
        if self.banner_timer > 0:
            self.banner_timer -= 1
        if self.shake > 0:
            self.shake -= 1

        if boss.hp <= 0:
            self.finish(SCENE_WIN)
        elif player.focus <= 0:
            self.finish(SCENE_LOSE)

    def finish(self, scene):
        self.scene = scene
        self.end_timer = 0
        self.shake = 0
        pyxel.stop()
        if scene == SCENE_WIN:
            for b in bullets:
                b.is_alive = False
            cleanup(bullets)
            for _ in range(8):
                Spark(self.boss.x + pyxel.rndf(-14, 14), self.boss.y + pyxel.rndf(-14, 14), 10)
            pyxel.play(3, 6)
        else:
            pyxel.play(3, 7)

    # --- draw --------------------------------------------------------------

    def draw(self):
        pyxel.cls(1)
        if self.shake > 0:
            pyxel.camera(pyxel.rndi(-2, 2), pyxel.rndi(-2, 2))
        self.draw_office()

        if self.scene == SCENE_TITLE:
            pyxel.camera()
            self.draw_title()
            return

        self.boss.draw()
        for group in (pickups, shots, bullets, effects):
            for e in group:
                e.draw()
        if self.scene == SCENE_PLAY or self.scene == SCENE_WIN:
            self.player.draw()
        pyxel.camera()
        self.draw_hud()

        if self.scene == SCENE_WIN:
            self.draw_end("FEATURE SHIPPED!", 11, WIN_LINE)
        elif self.scene == SCENE_LOSE:
            self.draw_end("PULLED INTO A MEETING", 8, LOSE_LINE)

    def draw_office(self):
        # Scrolling carpet tiles + cubicle dividers
        off = (pyxel.frame_count // 2) % 20
        for y in range(-20, H, 20):
            for x in range(0, W, 20):
                if ((x // 20) + ((y + off) // 20)) % 2 == 0:
                    pyxel.rect(x, y + off, 20, 20, 5 if self.scene != SCENE_TITLE else 1)
        for y in range(-40, H, 40):
            yy = y + (pyxel.frame_count // 2) % 40
            pyxel.rect(0, yy, 6, 3, 13)
            pyxel.rect(W - 6, yy, 6, 3, 13)
        pyxel.dither(0.5)
        pyxel.rect(0, 0, W, H, 1)
        pyxel.dither(1.0)

    def draw_hud(self):
        boss, player = self.boss, self.player

        # Boss bar
        pyxel.rect(0, 0, W, 11, 0)
        pyxel.text(3, 3, "URGE TO SYNC", 14)
        bar_x, bar_w = 54, W - 58
        pyxel.rectb(bar_x, 2, bar_w, 7, 13)
        fill = max(0, int((bar_w - 2) * boss.hp / BOSS_HP))
        pyxel.rect(bar_x + 1, 3, fill, 5, 8 if boss.phase >= 4 else 14)

        # Slack-style toast from the manager
        if self.toast_timer > 0 and self.scene == SCENE_PLAY:
            msg = self.toast_text
            tw = max(text_w(msg), 48) + 20
            tx = (W - tw) // 2
            pyxel.rect(tx, 14, tw, 17, 7)
            pyxel.rectb(tx, 14, tw, 17, 13)
            pyxel.blt(tx + 2, 15, 0, *SPR_MANAGER, 16, 16, 0, scale=0.9)
            pyxel.text(tx + 18, 16, "Your Manager", 2)
            pyxel.text(tx + 18, 23, msg, 0)

        # Bottom bar: focus, DND, status, LOC
        pyxel.rect(0, H - 11, W, 11, 0)
        pyxel.text(3, H - 8, "FOCUS", 7)
        for i in range(PLAYER_FOCUS):
            if i < player.focus:
                pyxel.blt(25 + i * 9, H - 10, 0, *SPR_COFFEE, 8, 8, 0)
            else:
                pyxel.rectb(26 + i * 9, H - 8, 6, 5, 5)
        pyxel.text(75, H - 8, "DND", 7)
        for i in range(player.dnd):
            pyxel.rect(89 + i * 6, H - 8, 4, 5, 11)
        if player.status_timer > 0:
            status, col = "In a meeting", 8
        else:
            status, col = "Heads down", 11
        pyxel.circ(112, H - 6, 2, col)
        pyxel.text(117, H - 8, status, 13)
        loc = f"{App.stats['loc']:6}"
        pyxel.text(W - text_w(loc) - 14, H - 8, loc, 10)
        pyxel.text(W - 13, H - 8, "LOC", 13)

        if self.banner_timer > 0:
            big_text(W / 2, H / 2 - 4, self.banner_text, self.banner_col, 2)

    def draw_title(self):
        pyxel.rect(0, 0, W, H, 1)
        self.draw_office()
        bob = math.sin(pyxel.frame_count * 0.05) * 3
        big_text(W / 2, 34, "QUICK SYNC?", 10, 3)
        center_text(56, "a meeting-dodging boss fight", 13)

        pyxel.blt(W / 2 - 12, 78 + bob, 0, *SPR_MANAGER, 16, 16, 0, scale=2.5)
        # The manager's opening line, cycling
        lines = SYNC_TEXTS + [BIG_CHAT_FULL]
        line = lines[(pyxel.frame_count // 90) % len(lines)]
        bx = W / 2 + 6
        tw = text_w(line) + 6
        bx = min(bx, W - tw - 4)
        pyxel.rect(bx, 64 + bob, tw, 9, 7)
        pyxel.text(bx + 3, 66 + bob, line, 1)

        y = 116
        for keys, desc in [
            ("ARROWS/WASD", "move  (SHIFT: careful)"),
            ("Z / SPACE", "ship code (hold)"),
            ("X", "do not disturb (x3)"),
        ]:
            pyxel.text(30, y, keys, 10)
            pyxel.text(82, y, desc, 7)
            y += 10
        center_text(152, "Dodge the interruptions. Grab coffee.", 13)
        center_text(160, "Drain the manager's urge to sync.", 13)
        if pyxel.frame_count % 40 < 28:
            center_text(178, "- PRESS ENTER -", 7)

    def draw_end(self, title, col, line):
        pyxel.dither(0.75)
        pyxel.rect(0, 50, W, 100, 0)
        pyxel.dither(1.0)
        big_text(W / 2, 62, title, col, 2 if len(title) < 18 else 1.5)
        center_text(80, f'"{line}"', 7)
        s = App.stats
        secs = s["frames"] // 60
        rows = [
            ("Lines of code shipped", f"{s['loc']}"),
            ("Interruptions dodged", f"{s['dodged']}"),
            ("Invites declined", f"{s['declined']}"),
            ("Meetings attended", f"{s['meetings']}"),
            ("Time in flow", f"{secs // 60}m {secs % 60:02}s"),
        ]
        y = 96
        for k, v in rows:
            pyxel.text(30, y, k, 13)
            pyxel.text(W - 30 - text_w(v), y, v, 10)
            y += 9
        if self.end_timer > 60 and pyxel.frame_count % 40 < 28:
            center_text(142, "- PRESS ENTER -", 7)


if __name__ == "__main__":
    App()
