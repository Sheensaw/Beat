import asyncio
import platform
import pygame
import sys
import random
from PIL import Image
import math

# ────────────────────────────────────────────────
# CONFIGURATION GÉNÉRALE
# ────────────────────────────────────────────────
WIDTH, HEIGHT = 800, 600
WORLD_WIDTH   = 3200
FPS           = 60
GRAVITY       = 0.8
DESPAWN_MARGIN = 360  # Augmenté (1.5x)
SPAWN_MARGIN = 150    # Augmenté (1.5x)

# Joueur
PLAYER_SPEED        = 5
PLAYER_JUMP         = 15
PLAYER_MAX_HP       = 50
INVULN_FRAMES       = 30
KNOCKBACK_X         = 6
KNOCKBACK_Y         = -4
BULLET_SPEED        = 10

# Shooter ennemi
SHO_HP, SHO_DMG     = 3, 1
SHO_SPEED_RANGE     = (1, 3)
SHO_SHOT_INTERVAL   = (1200, 2000)
SHO_JUMP_CD         = 1000
SHO_RANGE           = 200
SHO_SAFE_DIST       = 120

# Melee ennemi
MEL_HP, MEL_DMG     = 4, 1
MEL_SPEED_RANGE     = (1, 3)
MEL_JUMP_CD         = 800
MEL_LOOKAHEAD       = 36  # Augmenté (1.5x)
MEL_DROP_H          = 50
MEL_MIN_DIST        = 20

# Vehicle ennemi
VEH_HP, VEH_DMG     = 2, 1
VEH_SPEED_RANGE     = (3, 5)

# Couleurs
SKY_FAR   = (183, 217, 255)
CITY_MID  = (124, 141, 181)
TREE_NEAR = (60, 114, 66)
C_BG       = (126, 200, 235)
C_PLATFORM = (139,  69,  19)
C_PLAYER   = ( 20,  20, 255)
C_SHOOTER  = (220,  40,  40)
C_MELEE    = ( 40, 220,  40)
C_VEHICLE  = (  0,   0,   0)
C_BULLET   = ( 10,  10,  10)
C_BAR_BG   = ( 40,  40,  40)
C_BAR      = (  0, 255,   0)
C_ARROW    = (255, 255,   0)

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Parallax Beat'em Up")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 48)  # Augmenté pour visibilité
big_font = pygame.font.SysFont(None, 48)
hit_font = pygame.font.SysFont(None, 72)  # Augmenté pour visibilité

# ────────────────────────────────────────────────
# CHARGEMENT DES ANIMATIONS
# ────────────────────────────────────────────────
def load_gif_frames(gif_path, target_height=144):  # Augmenté à 144 pour personnages
    gif = Image.open(gif_path)
    frames = []
    durations = []
    for frame in range(gif.n_frames):
        gif.seek(frame)
        frame_image = gif.convert("RGBA")
        scale_factor = target_height / frame_image.height
        new_width = int(frame_image.width * scale_factor)
        frame_image = frame_image.resize((new_width, target_height), Image.LANCZOS)
        mode = frame_image.mode
        size = frame_image.size
        data = frame_image.tobytes()
        frame_surface = pygame.image.fromstring(data, size, mode)
        frames.append(frame_surface)
        duration = gif.info.get('duration', 100) / 1000
        durations.append(duration)
    return frames, durations

melee_walk_frames, melee_walk_durations = load_gif_frames("gifs/melee_walk.gif")
melee_idle_frames, melee_idle_durations = load_gif_frames("gifs/melee_idle.gif")
melee_2_walk_frames, melee_2_walk_durations = load_gif_frames("gifs/melee_2_walk.gif")
melee_2_idle_frames, melee_2_idle_durations = load_gif_frames("gifs/melee_2_idle.gif")
shooter_idle_frames, shooter_idle_durations = load_gif_frames("gifs/shooter_idle.gif")
shooter_walk_frames, shooter_walk_durations = load_gif_frames("gifs/shooter_walk.gif")
shooter_attack_frames, shooter_attack_durations = load_gif_frames("gifs/shooter_attack.gif")
projectile_frames, projectile_durations = load_gif_frames("gifs/shooter_projectile.gif", target_height=36)  # Augmenté

# ────────────────────────────────────────────────
# GÉNÉRATION DES PLANS DE PARALLAXE
# ────────────────────────────────────────────────
def make_far(w):
    surf = pygame.Surface((w, HEIGHT))
    surf.fill(SKY_FAR)
    for y in range(-40, HEIGHT, 120):
        pygame.draw.polygon(surf, (255, 255, 255, 60),
                            [(0, y), (w, y + 40), (w, y + 60), (0, y + 20)])
    return surf

def make_mid(w):
    building_img = pygame.image.load("layers/building_layer.png").convert_alpha()
    orig_width, orig_height = building_img.get_size()
    target_height = HEIGHT - 60  # Ajusté pour éviter chevauchement
    scale_factor = target_height / orig_height
    new_width = int(orig_width * scale_factor)
    scaled_img = pygame.transform.scale(building_img, (new_width, target_height))
    surf = pygame.Surface((w, HEIGHT), pygame.SRCALPHA)
    num_repeats = math.ceil(w / new_width) + 1
    for i in range(num_repeats):
        surf.blit(scaled_img, (i * new_width, 0))
    return surf

def make_near(w):
    surf = pygame.Surface((w, HEIGHT), pygame.SRCALPHA)
    for x in range(0, w, 360):  # Espacement augmenté (1.5x)
        pygame.draw.rect(surf, (91, 50, 14), (x + 141, HEIGHT - 300, 18, 180))  # Tronc 1.5x
        pygame.draw.circle(surf, TREE_NEAR, (x + 150, HEIGHT - 300), 102)  # Feuillage 1.5x
    return surf

far_layer  = make_far(WORLD_WIDTH)
mid_layer  = make_mid(WORLD_WIDTH)
near_layer = make_near(WORLD_WIDTH)

def draw_parallax(cx):
    screen.blit(far_layer, (-cx * 0.25, 0))
    screen.blit(mid_layer, (-cx * 0.5, 0))
    screen.blit(near_layer, (-cx * 0.8, 0))

# ────────────────────────────────────────────────
# ARÈNES & VAGUES
# ────────────────────────────────────────────────
ARENAS = [
    {"x": 950, "width": int(1.5 * WIDTH), "waves": [{"s":3, "m":2, "v":0}]},
    {"x": 1850, "width": int(1.5 * WIDTH), "waves": [{"s":4, "m":3, "v":1}]},
    {"x": 2750, "width": int(1.5 * WIDTH), "waves": [{"s":4, "m":3, "v":1}, {"s":0, "m":5, "v":1}]},
]

# ────────────────────────────────────────────────
# OUTIL : détection de sol sous un rect
# ────────────────────────────────────────────────
def platform_below(rect, plats, dx=0):
    probe = rect.move(dx, 2)
    return any(probe.colliderect(p) and probe.bottom <= p.top + 4 for p in plats)

# ────────────────────────────────────────────────
# PLATEFORME SOL
# ────────────────────────────────────────────────
platforms = [pygame.Rect(0, HEIGHT - 40, WORLD_WIDTH, 40)]

# ────────────────────────────────────────────────
# CLASSES ENTITÉS
# ────────────────────────────────────────────────
class Player:
    def __init__(self):
        self.img = pygame.Surface((84, 144))  # Augmenté (1.5x)
        self.img.fill(C_PLAYER)
        self.rect = self.img.get_rect(midbottom=(100, HEIGHT - 40))
        self.vel = pygame.Vector2(0, 0)
        self.on_ground = False
        self.facing = 1
        self.hp = PLAYER_MAX_HP
        self.inv = 0

    def damage(self, dmg, direction):
        if self.inv: return
        self.hp -= dmg
        self.inv = INVULN_FRAMES
        self.vel.x, self.vel.y = KNOCKBACK_X * direction, KNOCKBACK_Y
        if self.hp <= 0:
            pygame.quit(); sys.exit()

    def handle_input(self, bounds):
        keys = pygame.key.get_pressed()
        self.vel.x = 0
        if keys[pygame.K_q]:
            if not bounds or self.rect.left - PLAYER_SPEED >= bounds[0]:
                self.vel.x = -PLAYER_SPEED
        if keys[pygame.K_d]:
            if not bounds or self.rect.right + PLAYER_SPEED <= bounds[1]:
                self.vel.x = PLAYER_SPEED
        if keys[pygame.K_SPACE] and self.on_ground:
            self.vel.y = -PLAYER_JUMP
            self.on_ground = False
        if self.vel.x != 0:
            self.facing = 1 if self.vel.x > 0 else -1

    def update(self):
        self.vel.y += GRAVITY
        self.rect.x += self.vel.x
        self._collide('x')
        self.rect.y += self.vel.y
        self.on_ground = False
        self._collide('y')
        self.rect.clamp_ip(pygame.Rect(0, 0, WORLD_WIDTH, HEIGHT))
        if self.inv:
            self.inv -= 1

    def _collide(self, axis):
        for p in platforms:
            if self.rect.colliderect(p):
                if axis == 'x':
                    if self.vel.x > 0:
                        self.rect.right = p.left
                    elif self.vel.x < 0:
                        self.rect.left = p.right
                    self.vel.x = 0
                else:
                    if self.vel.y > 0:
                        self.rect.bottom = p.top
                        self.vel.y = 0
                        self.on_ground = True
                    elif self.vel.y < 0:
                        self.rect.top = p.bottom
                        self.vel.y = 0

    def draw(self, cx):
        if self.inv == 0 or (self.inv // 4) % 2 == 0:
            screen.blit(self.img, (self.rect.x - cx, self.rect.y))

class Bullet:
    def __init__(self, x, y, vx, owner):
        self.vx = vx
        self.owner = owner
        if owner == 'enemy':
            self.frames = projectile_frames
            self.durations = projectile_durations
            self.current_frame = 0
            self.frame_time = 0
            self.img = self.frames[0]
            self.rect = self.img.get_rect(center=(x, y))
        else:
            self.rect = pygame.Rect(x, y, 24, 12)  # Augmenté (1.5x)
            self.img = None

    def update(self):
        self.rect.x += self.vx
        if self.owner == 'enemy':
            self.frame_time += 1 / FPS
            if self.frame_time >= self.durations[int(self.current_frame)]:
                self.current_frame += 1
                self.frame_time = 0
                if self.current_frame >= len(self.frames):
                    self.current_frame = 0
            self.img = self.frames[int(self.current_frame)]
            if self.vx > 0:
                self.img = pygame.transform.flip(self.img, True, False)

    def draw(self, cx):
        if self.owner == 'enemy':
            screen.blit(self.img, (self.rect.x - cx, self.rect.y))
        else:
            pygame.draw.rect(screen, C_BULLET,
                             (self.rect.x - cx, self.rect.y, 24, 12))

    def off_screen(self):
        return self.rect.right < 0 or self.rect.left > WORLD_WIDTH

class Enemy:
    def __init__(self, x, y, color, hp, dmg):
        self.img = pygame.Surface((84, 84))  # Augmenté (1.5x)
        self.img.fill(color)
        self.rect = self.img.get_rect(topleft=(x, y))
        self.max_hp = hp
        self.hp = hp
        self.dmg = dmg
        self.vel_y = 0
        self.on_ground = False
        self.hit_timer = 0
        self.hit_scale = 1.0

    def apply_grav(self):
        self.vel_y += GRAVITY
        self.rect.y += self.vel_y
        self.on_ground = False
        for p in platforms:
            if self.rect.colliderect(p) and self.vel_y >= 0:
                self.rect.bottom = p.top
                self.vel_y = 0
                self.on_ground = True

    def take_hit(self):
        self.hit_timer = 0.3
        self.hit_scale = 2.0

    def update(self, player):
        if self.hit_timer > 0:
            self.hit_timer -= 1 / FPS
            self.hit_scale = max(1.0, self.hit_scale - (1.0 / 0.3) * (1 / FPS))
        return not self.despawn()

    def draw(self, cx):
        screen.blit(self.img, (self.rect.x - cx, self.rect.y))
        if self.hit_timer > 0:
            x = self.rect.x - cx
            y = self.rect.y - 18  # Ajusté pour plus grand sprite
            bar_width = 84 * self.hit_scale  # Augmenté
            bar_height = 12 * self.hit_scale  # Augmenté
            bar_surf = pygame.Surface((84, 12), pygame.SRCALPHA)
            pygame.draw.rect(bar_surf, C_BAR_BG, (0, 0, 84, 12))
            fill = int(84 * self.hp / self.max_hp)
            pygame.draw.rect(bar_surf, C_BAR, (0, 0, fill, 12))
            scaled_bar = pygame.transform.scale(bar_surf, (bar_width, bar_height))
            bar_x = x - (bar_width - 84) / 2
            bar_y = y - (bar_height - 12) / 2
            screen.blit(scaled_bar, (bar_x, bar_y))
            percentage = int(100 * self.hp / self.max_hp)
            text = (hit_font if self.hit_scale > 1.0 else font).render(str(percentage), True, (255, 255, 255))
            shadow = (hit_font if self.hit_scale > 1.0 else font).render(str(percentage), True, (0, 0, 0))
            text_rect = text.get_rect(center=(x + 42, y - 18))
            shadow_rect = shadow.get_rect(center=(x + 43, y - 17))
            screen.blit(shadow, shadow_rect)
            screen.blit(text, text_rect)

    def despawn(self):
        return (self.rect.right < -DESPAWN_MARGIN or
                self.rect.left > WORLD_WIDTH + DESPAWN_MARGIN)

class ShooterEnemy(Enemy):
    def __init__(self, x, y, direction):
        super().__init__(x, y, C_SHOOTER, SHO_HP, SHO_DMG)
        self.dir = direction
        self.speed = random.uniform(*SHO_SPEED_RANGE)
        self.last_shot = pygame.time.get_ticks()
        self.s_interval = random.randint(*SHO_SHOT_INTERVAL)
        self.last_jump = 0
        self.idle_frames = shooter_idle_frames
        self.walk_frames = shooter_walk_frames
        self.attack_frames = shooter_attack_frames
        self.idle_durations = shooter_idle_durations
        self.walk_durations = shooter_walk_durations
        self.attack_durations = shooter_attack_durations
        self.current_frame = 0
        self.frame_time = 0
        self.state = 'idle'
        self.attack_timer = 0
        self.img = self.idle_frames[0]
        self.rect = self.img.get_rect(topleft=(x, y))

    def update(self, player):
        now = pygame.time.get_ticks()
        dx = player.rect.centerx - self.rect.centerx
        if abs(dx) > SHO_SAFE_DIST:
            self.dir = 1 if dx > 0 else -1
        self.state = 'walk' if abs(self.rect.x - (self.rect.x + self.dir * self.speed)) > 0.01 else 'idle'
        if self.attack_timer > 0:
            self.state = 'attack'
            self.attack_timer -= 1 / FPS
        self.rect.x += self.dir * self.speed
        if not platform_below(self.rect, platforms, self.dir * 6):
            self.dir *= -1
        if (self.on_ground and abs(dx) < 60 and
            player.rect.centery < self.rect.centery and
            now - self.last_jump >= SHO_JUMP_CD):
            self.vel_y = -PLAYER_JUMP
            self.on_ground = False
            self.last_jump = now
        if now - self.last_shot >= self.s_interval and abs(dx) < SHO_RANGE:
            bullets.append(Bullet(self.rect.centerx,
                                  self.rect.centery,
                                  6 if dx > 0 else -6,
                                  'enemy'))
            self.last_shot = now
            self.state = 'attack'
            self.attack_timer = 0.5
        self.apply_grav()
        frames = {
            'idle': self.idle_frames,
            'walk': self.walk_frames,
            'attack': self.attack_frames
        }[self.state]
        durations = {
            'idle': self.idle_durations,
            'walk': self.walk_durations,
            'attack': self.attack_durations
        }[self.state]
        self.frame_time += 1 / FPS
        if self.current_frame >= len(frames):
            self.current_frame = 0
        if self.frame_time >= durations[int(self.current_frame)]:
            self.current_frame += 1
            self.frame_time = 0
            if self.current_frame >= len(frames):
                self.current_frame = 0
        self.img = frames[int(self.current_frame)]
        if self.dir == 1:
            self.img = pygame.transform.flip(self.img, True, False)
        return super().update(player)

class MeleeEnemy(Enemy):
    def __init__(self, x, y):
        super().__init__(x, y, C_MELEE, MEL_HP, MEL_DMG)
        self.speed = random.uniform(*MEL_SPEED_RANGE)
        self.last_jump = 0
        animation_set = random.choice([
            (melee_walk_frames, melee_idle_frames, melee_walk_durations, melee_idle_durations),
            (melee_2_walk_frames, melee_2_idle_frames, melee_2_walk_durations, melee_2_idle_durations)
        ])
        self.walk_frames = animation_set[0]
        self.idle_frames = animation_set[1]
        self.walk_durations = animation_set[2]
        self.idle_durations = animation_set[3]
        self.current_frame = 0
        self.frame_time = 0
        self.moving = False
        self.facing = 1
        self.img = self.idle_frames[0]
        self.rect = self.img.get_rect(topleft=(x, y))

    def update(self, player):
        now = pygame.time.get_ticks()
        dx = player.rect.centerx - self.rect.centerx
        dir = 1 if dx > 0 else -1
        self.facing = dir
        if abs(dx) > MEL_MIN_DIST:
            self.moving = True
            self.rect.x += dir * self.speed
        else:
            self.moving = False
        if (self.on_ground and
            not platform_below(self.rect, platforms, dir * MEL_LOOKAHEAD)):
            self.vel_y = -PLAYER_JUMP
            self.on_ground = False
        if (self.on_ground and player.rect.centery < self.rect.centery - 20 and
            now - self.last_jump >= MEL_JUMP_CD):
            self.vel_y = -PLAYER_JUMP
            self.on_ground = False
            self.last_jump = now
        self.apply_grav()
        frames = self.walk_frames if self.moving else self.idle_frames
        durations = self.walk_durations if self.moving else self.idle_durations
        self.frame_time += 1 / FPS
        if self.current_frame >= len(frames):
            self.current_frame = 0
        if self.frame_time >= durations[int(self.current_frame)]:
            self.current_frame += 1
            self.frame_time = 0
            if self.current_frame >= len(frames):
                self.current_frame = 0
        self.img = frames[int(self.current_frame)]
        if self.facing == 1:
            self.img = pygame.transform.flip(self.img, True, False)
        return super().update(player)

    def draw(self, cx):
        screen.blit(self.img, (self.rect.x - cx, self.rect.y))
        if self.hit_timer > 0:
            x = self.rect.x - cx
            y = self.rect.y - 18
            bar_width = self.rect.w * self.hit_scale
            bar_height = 12 * self.hit_scale
            bar_surf = pygame.Surface((self.rect.w, 12), pygame.SRCALPHA)
            pygame.draw.rect(bar_surf, C_BAR_BG, (0, 0, self.rect.w, 12))
            fill = int(self.rect.w * self.hp / self.max_hp)
            pygame.draw.rect(bar_surf, C_BAR, (0, 0, fill, 12))
            scaled_bar = pygame.transform.scale(bar_surf, (bar_width, bar_height))
            bar_x = x - (bar_width - self.rect.w) / 2
            bar_y = y - (bar_height - 12) / 2
            screen.blit(scaled_bar, (bar_x, bar_y))
            percentage = int(100 * self.hp / self.max_hp)
            text = (hit_font if self.hit_scale > 1.0 else font).render(str(percentage), True, (255, 255, 255))
            shadow = (hit_font if self.hit_scale > 1.0 else font).render(str(percentage), True, (0, 0, 0))
            text_rect = text.get_rect(center=(x + self.rect.w / 2, y - 18))
            shadow_rect = shadow.get_rect(center=(x + self.rect.w / 2 + 1, y - 17))
            screen.blit(shadow, shadow_rect)
            screen.blit(text, text_rect)

class VehicleEnemy(Enemy):
    def __init__(self, x, direction):
        super().__init__(x - 120 if direction > 0 else x + 120,  # Ajusté (1.5x)
                         HEIGHT - 180, C_VEHICLE, VEH_HP, VEH_DMG)  # Ajusté
        self.speed = direction * random.randint(*VEH_SPEED_RANGE)

    def update(self, player):
        self.rect.x += self.speed
        return super().update(player)

# ────────────────────────────────────────────────
# FONCTION DE SPAWN D'UNE VAGUE
# ────────────────────────────────────────────────
def spawn_wave(w, left, right, is_arena=False):
    for _ in range(w["s"]):
        side = random.choice(['left', 'right'])
        x = left - SPAWN_MARGIN if side == 'left' else right + SPAWN_MARGIN
        enemies.append(ShooterEnemy(x, platforms[0].top - 144, 1 if side == 'left' else -1))
    for _ in range(w["m"]):
        side = random.choice(['left', 'right'])
        x = left - SPAWN_MARGIN if side == 'left' else right + SPAWN_MARGIN
        enemies.append(MeleeEnemy(x, platforms[0].top - 144))
    for _ in range(w["v"]):
        side = random.choice(['left', 'right'])
        x = left - SPAWN_MARGIN if side == 'left' else right + SPAWN_MARGIN
        enemies.append(VehicleEnemy(x, 1 if side == 'left' else -1))

# ────────────────────────────────────────────────
# INITIALISATION ÉTAT GLOBAL
# ────────────────────────────────────────────────
player = Player()
bullets = []
enemies = []

arena_idx = 0
arena_locked = None
arena_bounds = None
pending_waves = []
clear_timer = 0
show_arrow = False
camera_transition = False
transition_timer = 0
start_cam_x = 0
non_arena_spawn_timer = random.uniform(2, 5)

def fire_bullet():
    bullets.append(Bullet(player.rect.centerx + player.facing * 45,  # Ajusté (1.5x)
                          player.rect.centery,
                          player.facing * BULLET_SPEED,
                          'player'))

# ────────────────────────────────────────────────
# BOUCLE PRINCIPALE ASYNC
# ────────────────────────────────────────────────
async def main():
    global arena_idx, arena_locked, arena_bounds, pending_waves, clear_timer, show_arrow
    global camera_transition, transition_timer, start_cam_x, non_arena_spawn_timer
    while True:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                fire_bullet()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_KP0:
                fire_bullet()

        if arena_idx < len(ARENAS):
            if player.rect.centerx >= ARENAS[arena_idx]["x"] and arena_locked is None:
                enemies.clear()
                arena_locked = max(0, player.rect.centerx - WIDTH // 2)
                arena_bounds = (arena_locked, arena_locked + ARENAS[arena_idx]["width"])
                pending_waves = list(ARENAS[arena_idx]["waves"])
                spawn_wave(pending_waves.pop(0), arena_bounds[0], arena_bounds[1], is_arena=True)

        if arena_locked and not enemies and not pending_waves:
            clear_timer += 1
            show_arrow = (clear_timer // 20) % 2 == 0
            if clear_timer >= 120:
                arena_locked = None
                arena_bounds = None
                arena_idx += 1
                camera_transition = True
                transition_timer = 0.5
                start_cam_x = cam_x
                clear_timer = 0
                show_arrow = False

        if arena_locked and not enemies and pending_waves:
            spawn_wave(pending_waves.pop(0), arena_bounds[0], arena_bounds[1], is_arena=True)

        if arena_locked is None:
            non_arena_spawn_timer -= 1 / FPS
            if non_arena_spawn_timer <= 0:
                wave = {"s": random.randint(0, 1), "m": random.randint(1, 2), "v": random.randint(0, 1)}
                spawn_wave(wave, cam_x, cam_x + WIDTH)
                non_arena_spawn_timer = random.uniform(2, 5)

        player.handle_input(arena_bounds)
        player.update()

        for e in enemies[:]:
            if e.rect.right < cam_x - DESPAWN_MARGIN:
                enemies.remove(e)
                wave = {"s": random.randint(0, 1), "m": random.randint(0, 1), "v": random.randint(0, 1)}
                spawn_wave(wave, cam_x + WIDTH, cam_x + WIDTH + SPAWN_MARGIN)
                continue
            if not e.update(player):
                enemies.remove(e)
                continue
            if e.rect.colliderect(player.rect):
                direction = -1 if e.rect.centerx > player.rect.centerx else 1
                player.damage(e.dmg, direction)

        for b in bullets[:]:
            b.update()
            if b.off_screen():
                bullets.remove(b)
                continue
            if b.owner == 'player':
                for e in enemies[:]:
                    if b.rect.colliderect(e.rect):
                        e.hp -= 1
                        e.take_hit()
                        bullets.remove(b)
                        if e.hp <= 0:
                            enemies.remove(e)
                        break
            else:
                if b.rect.colliderect(player.rect):
                    direction = -1 if b.vx > 0 else 1
                    player.damage(1, direction)
                    bullets.remove(b)

        if camera_transition:
            transition_timer -= 1 / FPS
            if transition_timer <= 0:
                camera_transition = False
                cam_x = max(0, min(player.rect.centerx - WIDTH // 2, WORLD_WIDTH - WIDTH))
            else:
                t = 1 - (transition_timer / 0.5)
                target_x = max(0, min(player.rect.centerx - WIDTH // 2, WORLD_WIDTH - WIDTH))
                cam_x = start_cam_x + t * (target_x - start_cam_x)
        else:
            cam_x = arena_locked if arena_locked is not None else \
                    max(0, min(player.rect.centerx - WIDTH // 2, WORLD_WIDTH - WIDTH))

        screen.fill(C_BG)
        draw_parallax(cam_x)

        for p in platforms:
            pygame.draw.rect(screen, C_PLATFORM,
                             (p.x - cam_x, p.y, p.w, p.h))

        for b in bullets:
            b.draw(cam_x)
        for e in enemies:
            e.draw(cam_x)
        player.draw(cam_x)

        pygame.draw.rect(screen, C_BAR_BG, (10, 10, 120, 8))
        pygame.draw.rect(screen, C_BAR,
                         (10, 10, int(120 * player.hp / PLAYER_MAX_HP), 8))
        screen.blit(font.render(f"{player.hp}/{PLAYER_MAX_HP}",
                                True, (0, 0, 0)), (10, 22))
        screen.blit(font.render(f"Arène {arena_idx}/{len(ARENAS)}",
                                True, (0, 0, 0)), (WIDTH - 170, 10))

        if arena_locked and not enemies and not pending_waves:
            text = big_font.render("Arène terminée !", True, (255, 255, 255))
            text_rect = text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
            screen.blit(text, text_rect)
            if show_arrow:
                pygame.draw.polygon(screen, C_ARROW,
                                    [(WIDTH - 50, HEIGHT // 2),
                                     (WIDTH - 30, HEIGHT // 2 - 20),
                                     (WIDTH - 30, HEIGHT // 2 + 20)])

        pygame.display.flip()
        await asyncio.sleep(0)

# ────────────────────────────────────────────────
# LANCEMENT
# ────────────────────────────────────────────────
if platform.system() == "Emscripten":
    asyncio.ensure_future(main())
else:
    if __name__ == "__main__":
        asyncio.run(main())