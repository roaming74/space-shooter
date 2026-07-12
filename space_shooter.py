import pygame
import random
import sys
import array
import os
import json

# --- Настройки игры ---
WIDTH, HEIGHT = 600, 800
FPS = 60
SAMPLE_RATE = 44100

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 60, 60)
GREEN = (60, 255, 120)
YELLOW = (255, 230, 60)
BLUE = (60, 160, 255)
GRAY = (90, 90, 100)
LIGHT_GRAY = (140, 140, 150)

SAVE_PATH = os.path.join(os.path.expanduser("~"), ".space_shooter_save.json")

pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, 512)
pygame.init()


def build_icon_surface():
    icon = pygame.Surface((32, 32), pygame.SRCALPHA)
    pygame.draw.circle(icon, (15, 15, 35), (16, 16), 16)
    pygame.draw.polygon(icon, (70, 160, 255), [(16, 3), (5, 26), (27, 26)])
    pygame.draw.circle(icon, (180, 230, 255), (16, 16), 4)
    pygame.draw.polygon(icon, (255, 210, 60), [(12, 26), (20, 26), (16, 31)])
    return icon


pygame.display.set_icon(build_icon_surface())
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Космическая стрелялка")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 26)
big_font = pygame.font.SysFont("Arial", 46)
menu_font = pygame.font.SysFont("Arial", 34)


def draw_text(text, font_obj, color, x, y, center=True):
    surface = font_obj.render(text, True, color)
    rect = surface.get_rect()
    if center:
        rect.center = (x, y)
    else:
        rect.topleft = (x, y)
    screen.blit(surface, rect)


# ---------- Сохранение данных ----------

def load_save():
    if os.path.exists(SAVE_PATH):
        try:
            with open(SAVE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def write_save(data):
    try:
        with open(SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception:
        pass


save_data = load_save()
player_nickname = save_data.get("nickname")
music_volume = save_data.get("music_volume", 0.5)
sound_volume = save_data.get("sound_volume", 0.5)


def persist_save():
    write_save({
        "nickname": player_nickname,
        "music_volume": music_volume,
        "sound_volume": sound_volume,
    })


# ---------- Звук (генерируется без файлов, чисто кодом) ----------

def square_wave_bytes(frequency, duration_ms, volume=0.4):
    n_samples = int(SAMPLE_RATE * duration_ms / 1000)
    if frequency <= 0:
        period = n_samples * 2
    else:
        period = SAMPLE_RATE / frequency
    amp = int(32767 * volume)
    buf = array.array('h')
    for i in range(n_samples):
        val = amp if (i % period) < (period / 2) else -amp
        buf.append(val)
        buf.append(val)
    return buf


def make_sound(buf):
    return pygame.mixer.Sound(buffer=buf.tobytes())


def build_melody():
    notes = [523, 659, 784, 659, 523, 440, 523, 659,
             587, 698, 880, 698, 587, 494, 587, 698]
    dur = 200
    full = array.array('h')
    for note in notes:
        full.extend(square_wave_bytes(note, dur, volume=0.12))
        full.extend(square_wave_bytes(0, 15, volume=0))
    return full


def build_explosion():
    n_samples = int(SAMPLE_RATE * 0.25)
    buf = array.array('h')
    for i in range(n_samples):
        envelope = 1 - (i / n_samples)
        val = int(random.randint(-32767, 32767) * envelope * 0.4)
        buf.append(val)
        buf.append(val)
    return buf


music_sound = make_sound(build_melody())
shoot_sound = make_sound(square_wave_bytes(880, 70, volume=0.25))
explosion_sound = make_sound(build_explosion())
music_channel = pygame.mixer.Channel(0)


def apply_volumes():
    music_channel.set_volume(music_volume)
    shoot_sound.set_volume(sound_volume)
    explosion_sound.set_volume(sound_volume)


def start_music():
    if not music_channel.get_busy():
        music_channel.play(music_sound, loops=-1)


apply_volumes()

# ---------- Кнопки и ползунки ----------

class Button:
    def __init__(self, x, y, w, h, text):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text

    def draw(self):
        mouse_pos = pygame.mouse.get_pos()
        hovered = self.rect.collidepoint(mouse_pos)
        color = LIGHT_GRAY if hovered else GRAY
        pygame.draw.rect(screen, color, self.rect, border_radius=10)
        pygame.draw.rect(screen, WHITE, self.rect, width=2, border_radius=10)
        draw_text(self.text, menu_font, WHITE, self.rect.centerx, self.rect.centery)

    def is_clicked(self, event):
        return event.type == pygame.MOUSEBUTTONDOWN and self.rect.collidepoint(event.pos)


class Slider:
    def __init__(self, x, y, w, label, value):
        self.rect = pygame.Rect(x, y, w, 10)
        self.label = label
        self.value = value
        self.dragging = False
        self.handle_radius = 12

    def handle_pos(self):
        return self.rect.x + int(self.value * self.rect.width)

    def draw(self):
        draw_text(f"{self.label}: {int(self.value * 100)}%", font, WHITE, self.rect.centerx, self.rect.y - 22)
        pygame.draw.rect(screen, GRAY, self.rect, border_radius=5)
        pygame.draw.circle(screen, YELLOW, (self.handle_pos(), self.rect.centery), self.handle_radius)

    def handle_event(self, event):
        changed = False
        if event.type == pygame.MOUSEBUTTONDOWN:
            hx, hy = self.handle_pos(), self.rect.centery
            if (event.pos[0] - hx) ** 2 + (event.pos[1] - hy) ** 2 <= (self.handle_radius + 8) ** 2:
                self.dragging = True
        elif event.type == pygame.MOUSEBUTTONUP:
            if self.dragging:
                changed = True
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            rel_x = event.pos[0] - self.rect.x
            self.value = max(0.0, min(1.0, rel_x / self.rect.width))
        return changed


# ---------- Игровые объекты ----------

class Star:
    def __init__(self):
        self.x = random.randint(0, WIDTH)
        self.y = random.randint(0, HEIGHT)
        self.speed = random.uniform(1, 4)
        self.size = random.randint(1, 3)

    def update(self):
        self.y += self.speed
        if self.y > HEIGHT:
            self.y = 0
            self.x = random.randint(0, WIDTH)

    def draw(self):
        pygame.draw.circle(screen, WHITE, (int(self.x), int(self.y)), self.size)


class Player:
    def __init__(self):
        self.width = 50
        self.height = 40
        self.x = WIDTH // 2 - self.width // 2
        self.y = HEIGHT - 100
        self.speed = 7
        self.cooldown = 0
        self.lives = 3
        self.shield_timer = 0
        self.triple_timer = 0

    def update(self, keys):
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.x -= self.speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.x += self.speed
        self.x = max(0, min(WIDTH - self.width, self.x))
        if self.cooldown > 0:
            self.cooldown -= 1
        if self.shield_timer > 0:
            self.shield_timer -= 1
        if self.triple_timer > 0:
            self.triple_timer -= 1

    def shoot(self, bullets):
        if self.cooldown == 0:
            cx = self.x + self.width // 2
            if self.triple_timer > 0:
                bullets.append(Bullet(cx - 18, self.y))
                bullets.append(Bullet(cx, self.y))
                bullets.append(Bullet(cx + 18, self.y))
            else:
                bullets.append(Bullet(cx, self.y))
            shoot_sound.play()
            self.cooldown = 15

    def draw(self):
        cx = self.x + self.width // 2
        pygame.draw.polygon(
            screen, BLUE,
            [(cx, self.y), (self.x, self.y + self.height), (self.x + self.width, self.y + self.height)],
        )
        pygame.draw.polygon(
            screen, YELLOW,
            [(cx - 8, self.y + self.height), (cx + 8, self.y + self.height), (cx, self.y + self.height + 15)],
        )
        if self.shield_timer > 0:
            radius = max(self.width, self.height) // 2 + 14
            pygame.draw.circle(screen, (80, 220, 255), (cx, self.y + self.height // 2), radius, width=3)

    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)


class Bullet:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.speed = 10
        self.radius = 4

    def update(self):
        self.y -= self.speed

    def draw(self):
        pygame.draw.circle(screen, GREEN, (int(self.x), int(self.y)), self.radius)

    def get_rect(self):
        return pygame.Rect(self.x - self.radius, self.y - self.radius, self.radius * 2, self.radius * 2)


class Enemy:
    def __init__(self, level):
        self.width = 40
        self.height = 30
        self.x = random.randint(0, WIDTH - self.width)
        self.y = random.randint(-200, -40)
        self.speed = random.uniform(2, 3 + level * 0.3)
        self.hp = 1
        self.max_hp = 1

    def update(self):
        self.y += self.speed

    def draw(self):
        pygame.draw.rect(screen, RED, (self.x, self.y, self.width, self.height), border_radius=6)
        pygame.draw.circle(screen, YELLOW, (int(self.x + self.width // 2), int(self.y + self.height)), 5)

    def get_rect(self):
        return pygame.Rect(self.x, self.y, self.width, self.height)


class Enemy2(Enemy):
    """Враг 2-го уровня - крепче и быстрее, появляется после 20 секунд выживания."""

    def __init__(self, level):
        super().__init__(level)
        self.width = 54
        self.height = 40
        self.x = random.randint(0, WIDTH - self.width)
        self.speed = random.uniform(3.5, 4.5 + level * 0.3)
        self.hp = 2
        self.max_hp = 2

    def draw(self):
        pygame.draw.rect(screen, (170, 40, 220), (self.x, self.y, self.width, self.height), border_radius=8)
        pygame.draw.polygon(
            screen, YELLOW,
            [(self.x + self.width // 2, self.y + self.height),
             (self.x + self.width // 2 - 10, self.y + self.height - 10),
             (self.x + self.width // 2 + 10, self.y + self.height - 10)],
        )
        # полоска здоровья
        bar_w = self.width
        hp_ratio = self.hp / self.max_hp
        pygame.draw.rect(screen, GRAY, (self.x, self.y - 8, bar_w, 5))
        pygame.draw.rect(screen, GREEN, (self.x, self.y - 8, int(bar_w * hp_ratio), 5))


class PowerUp:
    def __init__(self, x, y, kind):
        self.x = x
        self.y = y
        self.kind = kind  # "shield" или "triple"
        self.size = 26
        self.speed = 2.5

    def update(self):
        self.y += self.speed

    def draw(self):
        cx, cy = int(self.x), int(self.y)
        if self.kind == "shield":
            pygame.draw.circle(screen, (80, 220, 255), (cx, cy), self.size // 2)
            pygame.draw.circle(screen, WHITE, (cx, cy), self.size // 2, width=2)
            draw_text("Щ", font, BLACK, cx, cy)
        else:
            pygame.draw.polygon(
                screen, (255, 150, 40),
                [(cx, cy - 14), (cx + 14, cy), (cx, cy + 14), (cx - 14, cy)],
            )
            pygame.draw.polygon(
                screen, WHITE,
                [(cx, cy - 14), (cx + 14, cy), (cx, cy + 14), (cx - 14, cy)],
                width=2,
            )
            draw_text("3", font, BLACK, cx, cy)

    def get_rect(self):
        return pygame.Rect(self.x - self.size // 2, self.y - self.size // 2, self.size, self.size)


# ---------- Состояния игры ----------
STATE_NICKNAME = "nickname"
STATE_MENU = "menu"
STATE_GUIDE = "guide"
STATE_PLAYING = "playing"
STATE_GAME_OVER = "game_over"


def new_game_state():
    return {
        "player": Player(),
        "bullets": [],
        "enemies": [],
        "powerups": [],
        "score": 0,
        "level": 1,
        "spawn_timer": 0,
        "survival_frames": 0,
        "level_up_flash": 0,
    }


LEVEL_2_SECONDS = 20
POWERUP_DROP_CHANCE = 0.2
SHIELD_DURATION = FPS * 6
TRIPLE_DURATION = FPS * 8


def main():
    global player_nickname, music_volume, sound_volume

    stars = [Star() for _ in range(60)]
    state = STATE_NICKNAME if not player_nickname else STATE_MENU
    game = new_game_state()
    nickname_input = ""

    play_button = Button(WIDTH // 2 - 110, 430, 220, 60, "ИГРАТЬ")
    guide_button = Button(WIDTH // 2 - 110, 510, 220, 60, "ГАЙД")
    back_button = Button(WIDTH // 2 - 110, HEIGHT - 100, 220, 60, "НАЗАД")
    restart_button = Button(WIDTH // 2 - 230, HEIGHT // 2 + 60, 220, 60, "ИГРАТЬ СНОВА")
    menu_button = Button(WIDTH // 2 + 10, HEIGHT // 2 + 60, 220, 60, "МЕНЮ")

    music_slider = Slider(WIDTH // 2 - 120, 640, 240, "Музыка", music_volume)
    sound_slider = Slider(WIDTH // 2 - 120, 700, 240, "Звуки", sound_volume)

    start_music()

    running = True
    while running:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if state == STATE_NICKNAME:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN and nickname_input.strip():
                        player_nickname = nickname_input.strip()[:12]
                        persist_save()
                        state = STATE_MENU
                    elif event.key == pygame.K_BACKSPACE:
                        nickname_input = nickname_input[:-1]
                    elif len(nickname_input) < 12 and event.unicode.isprintable():
                        nickname_input += event.unicode

            elif state == STATE_MENU:
                if play_button.is_clicked(event):
                    game = new_game_state()
                    state = STATE_PLAYING
                if guide_button.is_clicked(event):
                    state = STATE_GUIDE
                if music_slider.handle_event(event):
                    music_volume = music_slider.value
                    apply_volumes()
                    persist_save()
                if sound_slider.handle_event(event):
                    sound_volume = sound_slider.value
                    apply_volumes()
                    persist_save()

            elif state == STATE_GUIDE:
                if back_button.is_clicked(event):
                    state = STATE_MENU

            elif state == STATE_PLAYING:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    game["player"].shoot(game["bullets"])

            elif state == STATE_GAME_OVER:
                if restart_button.is_clicked(event):
                    game = new_game_state()
                    state = STATE_PLAYING
                if menu_button.is_clicked(event):
                    state = STATE_MENU

        # живое перетаскивание ползунков мышью (не только по клику)
        if state == STATE_MENU:
            music_volume = music_slider.value
            sound_volume = sound_slider.value
            apply_volumes()

        keys = pygame.key.get_pressed()
        screen.fill(BLACK)
        for star in stars:
            star.update()
            star.draw()

        if state == STATE_NICKNAME:
            draw_text("КОСМИЧЕСКАЯ СТРЕЛЯЛКА", big_font, YELLOW, WIDTH // 2, 250)
            draw_text("Как тебя зовут, космонавт?", font, WHITE, WIDTH // 2, 340)
            box_rect = pygame.Rect(WIDTH // 2 - 150, 380, 300, 50)
            pygame.draw.rect(screen, GRAY, box_rect, border_radius=8)
            pygame.draw.rect(screen, WHITE, box_rect, width=2, border_radius=8)
            draw_text(nickname_input or "|", font, WHITE, box_rect.centerx, box_rect.centery)
            draw_text("Нажми ENTER, чтобы подтвердить", font, LIGHT_GRAY, WIDTH // 2, 460)

        elif state == STATE_MENU:
            draw_text("КОСМИЧЕСКАЯ СТРЕЛЯЛКА", big_font, YELLOW, WIDTH // 2, 220)
            draw_text(f"Пилот: {player_nickname}", font, GREEN, WIDTH // 2, 280)
            play_button.draw()
            guide_button.draw()
            music_slider.draw()
            sound_slider.draw()

        elif state == STATE_GUIDE:
            draw_text("КАК ИГРАТЬ", big_font, YELLOW, WIDTH // 2, 150)
            lines = [
                "← → или A / D — двигать корабль",
                "ПРОБЕЛ — стрелять",
                "Уничтожай врагов, чтобы получать очки",
                "Не давай врагам долетать до низа экрана",
                "3 жизни — теряешь их, если враг",
                "долетел до низа или врезался в тебя",
                "Враги иногда роняют бонусы:",
                "синий щит — защита от урона",
                "оранжевый ромб — тройной выстрел",
                "Чем больше очков — тем выше уровень",
                "и тем быстрее враги!",
            ]
            y = 230
            for line in lines:
                draw_text(line, font, WHITE, WIDTH // 2, y)
                y += 45
            back_button.draw()

        elif state == STATE_PLAYING:
            player = game["player"]
            bullets = game["bullets"]
            enemies = game["enemies"]
            powerups = game["powerups"]

            player.update(keys)

            game["survival_frames"] += 1
            survival_seconds = game["survival_frames"] / FPS

            if game["level"] == 1 and survival_seconds >= LEVEL_2_SECONDS:
                game["level"] = 2
                game["level_up_flash"] = FPS * 2  # показать надпись 2 секунды

            if game["level_up_flash"] > 0:
                game["level_up_flash"] -= 1

            game["spawn_timer"] += 1
            spawn_rate = max(20, 60 - game["level"] * 8)
            if game["spawn_timer"] >= spawn_rate:
                if game["level"] >= 2:
                    enemies.append(Enemy2(game["level"]))
                else:
                    enemies.append(Enemy(game["level"]))
                game["spawn_timer"] = 0

            for bullet in bullets[:]:
                bullet.update()
                if bullet.y < 0:
                    bullets.remove(bullet)

            for enemy in enemies[:]:
                enemy.update()
                if enemy.y > HEIGHT:
                    enemies.remove(enemy)
                    player.lives -= 1
                    if player.lives <= 0:
                        state = STATE_GAME_OVER

            for bullet in bullets[:]:
                for enemy in enemies[:]:
                    if bullet.get_rect().colliderect(enemy.get_rect()):
                        if bullet in bullets:
                            bullets.remove(bullet)
                        enemy.hp -= 1
                        if enemy.hp <= 0:
                            if enemy in enemies:
                                enemies.remove(enemy)
                            explosion_sound.play()
                            game["score"] += 10 if enemy.max_hp == 1 else 25
                            if random.random() < POWERUP_DROP_CHANCE:
                                kind = random.choice(["shield", "triple"])
                                powerups.append(PowerUp(enemy.x + enemy.width // 2, enemy.y, kind))
                        break

            for enemy in enemies[:]:
                if player.get_rect().colliderect(enemy.get_rect()):
                    enemies.remove(enemy)
                    if player.shield_timer > 0:
                        explosion_sound.play()
                    else:
                        explosion_sound.play()
                        player.lives -= 1
                        if player.lives <= 0:
                            state = STATE_GAME_OVER

            for powerup in powerups[:]:
                powerup.update()
                if powerup.y > HEIGHT:
                    powerups.remove(powerup)
                elif player.get_rect().colliderect(powerup.get_rect()):
                    if powerup.kind == "shield":
                        player.shield_timer = SHIELD_DURATION
                    else:
                        player.triple_timer = TRIPLE_DURATION
                    powerups.remove(powerup)

            for bullet in bullets:
                bullet.draw()
            for enemy in enemies:
                enemy.draw()
            for powerup in powerups:
                powerup.draw()
            player.draw()

            draw_text(f"Очки: {game['score']}", font, WHITE, 80, 30)
            draw_text(f"Уровень: {game['level']}", font, WHITE, WIDTH - 100, 30)
            draw_text(f"Жизни: {player.lives}", font, GREEN, WIDTH // 2, 30)
            draw_text(f"Время: {int(survival_seconds)} сек", font, YELLOW, WIDTH // 2, 65)

            buff_y = 95
            if player.shield_timer > 0:
                draw_text(f"Щит: {player.shield_timer // FPS + 1} сек", font, (80, 220, 255), 100, buff_y, center=False)
                buff_y += 30
            if player.triple_timer > 0:
                draw_text(f"Тройной выстрел: {player.triple_timer // FPS + 1} сек", font, (255, 150, 40), 100, buff_y, center=False)

            if game["level_up_flash"] > 0:
                draw_text("УРОВЕНЬ 2! ВРАГИ СТАЛИ СИЛЬНЕЕ", menu_font, (255, 80, 220), WIDTH // 2, 100)

        elif state == STATE_GAME_OVER:
            for bullet in game["bullets"]:
                bullet.draw()
            for enemy in game["enemies"]:
                enemy.draw()

            draw_text("ИГРА ОКОНЧЕНА", big_font, RED, WIDTH // 2, HEIGHT // 2 - 60)
            draw_text(f"Твой счёт: {game['score']}", font, WHITE, WIDTH // 2, HEIGHT // 2 - 10)
            restart_button.draw()
            menu_button.draw()

        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
