import pygame
import sys
import random
import math
import time
from collections import deque

pygame.init()
pygame.mixer.init()

# --- Настройки окна ---
WIDTH, HEIGHT = 560, 620
TILE = 20
ROWS = HEIGHT // TILE
COLS = WIDTH // TILE
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Pac-Man Deluxe")

# --- Цвета ---
BLACK = (0, 0, 0)
BLUE = (33, 33, 255)
YELLOW = (255, 255, 0)
GREEN = (0, 255, 100)
WHITE = (255, 255, 255)
RED = (255, 60, 60)
GRAY = (150, 150, 150)
ORANGE = (255, 150, 0)
EXPLOSION_COLOR = (255, 200, 100)

# --- Настройки игры ---
MONSTER_TRIGGER_STEP = 30
CHASE_TIME = 5
MONSTER_SPEED = 1.8
PLAYER_SPEED = 2.2
BOMB_TIMER = 2.0
EXPLOSION_RADIUS = 60
EXPLOSION_DURATION = 0.5

clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 20)
menu_font = pygame.font.SysFont("Arial", 32)

# --- Звуки ---
try:
    snd_eat = pygame.mixer.Sound("eat.wav")
    snd_place = pygame.mixer.Sound("bomb_place.wav")
    snd_explode = pygame.mixer.Sound("bomb_explode.wav")
    snd_caught = pygame.mixer.Sound("caught.wav")
except:
    snd_eat = snd_place = snd_explode = snd_caught = None
    print("⚠️ Не найдены звуки! Положите файлы *.wav рядом с программой.")

# --- Генерация карты ---
def generate_random_maze(rows, cols, wall_density=0.15):
    maze = []
    for y in range(rows):
        row = ""
        for x in range(cols):
            if x == 0 or y == 0 or x == cols-1 or y == rows-1:
                row += "#"
            else:
                row += "#" if random.random() < wall_density else "."
        maze.append(row)
    return maze

def random_direction():
    return random.choice([(1,0), (-1,0), (0,1), (0,-1)])

def find_free_cell(maze):
    while True:
        x = random.randint(1, COLS-2)
        y = random.randint(1, ROWS-2)
        if maze[y][x] == ".":
            return x, y

# --- BFS ---
def bfs_path(maze, start, goal):
    queue = deque([start])
    came_from = {start: None}
    while queue:
        x, y = queue.popleft()
        if (x, y) == goal:
            break
        for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
            nx, ny = x+dx, y+dy
            if 0 <= nx < COLS and 0 <= ny < ROWS and maze[ny][nx] == "." and (nx, ny) not in came_from:
                came_from[(nx, ny)] = (x, y)
                queue.append((nx, ny))
    if goal not in came_from:
        return []
    path = []
    curr = goal
    while curr:
        path.append(curr)
        curr = came_from[curr]
    path.reverse()
    return path

def find_reachable(maze, start):
    visited = set([start])
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
            nx, ny = x+dx, y+dy
            if 0 <= nx < COLS and 0 <= ny < ROWS and maze[ny][nx] == "." and (nx, ny) not in visited:
                visited.add((nx, ny))
                queue.append((nx, ny))
    return visited

# --- Глобальные переменные ---
dead_players = 0
collected_dots = 0
monster_mode = "random"
chase_start_time = 0
next_trigger = MONSTER_TRIGGER_STEP
players = []
monsters = []
bombs = []
walls = []
dots = []

def reset_game(player_count):
    global maze, walls, dots, players, monsters, bombs
    global collected_dots, monster_mode, chase_start_time, next_trigger
    global dead_players

    dead_players = 0

    maze = generate_random_maze(ROWS, COLS, 0.15)
    px1, py1 = find_free_cell(maze)
    reachable = find_reachable(maze, (px1, py1))

    walls.clear()
    dots.clear()
    for y, row in enumerate(maze):
        for x, ch in enumerate(row):
            if ch == "#":
                walls.append(pygame.Rect(x*TILE, y*TILE, TILE, TILE))
            elif ch == "." and (x, y) in reachable:
                dots.append(pygame.Rect(x*TILE+8, y*TILE+8, 4, 4))

    px2, py2 = find_free_cell(maze)
    players.clear()

    # Первый игрок всегда есть
    players.append({
        "rect": pygame.Rect(px1*TILE+2, py1*TILE+2, TILE-4, TILE-4),
        "color": YELLOW, "vx": 0, "vy": 0, "angle": 0, "keys": {
            "left": pygame.K_LEFT, "right": pygame.K_RIGHT,
            "up": pygame.K_UP, "down": pygame.K_DOWN
        }, "dead": False
    })

    # Второй игрок, если выбран
    if player_count == 2:
        players.append({
            "rect": pygame.Rect(px2*TILE+2, py2*TILE+2, TILE-4, TILE-4),
            "color": GREEN, "vx": 0, "vy": 0, "angle": 0, "keys": {
                "left": pygame.K_a, "right": pygame.K_d,
                "up": pygame.K_w, "down": pygame.K_s
            }, "dead": False
        })

    monsters.clear()
    for _ in range(5):
        mx, my = find_free_cell(maze)
        dx, dy = random_direction()
        monsters.append({
            "cell": (mx, my), "rect": pygame.Rect(mx*TILE, my*TILE, TILE, TILE),
            "path": [], "dx": dx, "dy": dy
        })

    bombs.clear()
    collected_dots = 0
    monster_mode = "random"
    chase_start_time = 0
    next_trigger = MONSTER_TRIGGER_STEP

def can_move(rect, dx, dy):
    next_rect = rect.move(dx, dy)
    return not any(next_rect.colliderect(w) for w in walls)

def place_bomb(p):
    bombs.append({"pos": p["rect"].center, "spawn_time": time.time(), "exploded": False, "radius": 6})
    if snd_place: snd_place.play()

def process_bombs():
    global monsters
    now = time.time()
    for b in bombs[:]:
        if not b["exploded"] and now - b["spawn_time"] >= BOMB_TIMER:
            b["exploded"] = True
            b["explosion_time"] = now
            if snd_explode: snd_explode.play()
            bx, by = b["pos"]
            monsters = [m for m in monsters if math.hypot(m["rect"].centerx - bx, m["rect"].centery - by) > EXPLOSION_RADIUS]
        elif b["exploded"]:
            elapsed = now - b["explosion_time"]
            b["radius"] = int(EXPLOSION_RADIUS * min(1, elapsed / EXPLOSION_DURATION))
            if elapsed > EXPLOSION_DURATION:
                bombs.remove(b)

def draw_pacman(p):
    rect = p["rect"]
    angle = p["angle"]
    center = rect.center
    mouth_angle = abs(math.sin(pygame.time.get_ticks() * 0.01)) * 35 + 10
    start_angle = math.radians(mouth_angle)
    end_angle = math.radians(360 - mouth_angle)
    rotated_start = math.radians(angle)
    rotated_end = rotated_start + end_angle - start_angle
    pygame.draw.circle(screen, p["color"], center, TILE//2)
    pygame.draw.polygon(screen, BLACK, [
        center,
        (center[0] + math.cos(rotated_start) * TILE//2,
         center[1] + math.sin(rotated_start) * TILE//2),
        (center[0] + math.cos(rotated_end) * TILE//2,
         center[1] + math.sin(rotated_end) * TILE//2)
    ])

# --- Меню ---
def show_menu():
    selected = 0
    options = ["1 Игрок", "2 Игрока"]

    while True:
        screen.fill(BLACK)

        title = menu_font.render("Pac-Man Deluxe", True, YELLOW)
        screen.blit(title, (WIDTH//2 - title.get_width()//2, HEIGHT//4))

        for i, option in enumerate(options):
            color = WHITE if i == selected else GRAY
            text = menu_font.render(option, True, color)
            screen.blit(text, (WIDTH//2 - text.get_width()//2, HEIGHT//2 + i*50))

        info = font.render("Используйте ↑↓ и Enter для выбора", True, GRAY)
        screen.blit(info, (WIDTH//2 - info.get_width()//2, HEIGHT - 60))

        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    selected = (selected - 1) % len(options)
                elif event.key == pygame.K_DOWN:
                    selected = (selected + 1) % len(options)
                elif event.key == pygame.K_RETURN:
                    return selected + 1

        clock.tick(60)

# --- Основной цикл ---
def main():
    player_count = show_menu()
    reset_game(player_count)

    global dead_players, collected_dots, monster_mode, chase_start_time, next_trigger

    while True:
        screen.fill(BLACK)

        # События
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_r:
                    reset_game(player_count)
                for p in players:
                    if p.get("dead"):
                        continue
                    k = p["keys"]
                    if e.key == k["left"]:  p["vx"], p["vy"], p["angle"] = -PLAYER_SPEED, 0, 180
                    if e.key == k["right"]: p["vx"], p["vy"], p["angle"] = PLAYER_SPEED, 0, 0
                    if e.key == k["up"]:    p["vy"], p["vx"], p["angle"] = -PLAYER_SPEED, 0, 270
                    if e.key == k["down"]:  p["vy"], p["vx"], p["angle"] = PLAYER_SPEED, 0, 90
                if not players[0].get("dead") and e.key == pygame.K_SPACE:
                    place_bomb(players[0])
                if player_count == 2 and not players[1].get("dead") and e.key == pygame.K_f:
                    place_bomb(players[1])

        # Движение игроков
        for p in players:
            if p.get("dead"):
                continue
            rect = p["rect"]
            if can_move(rect, p["vx"], p["vy"]):
                rect.x += p["vx"]
                rect.y += p["vy"]

        # Точки
        for dot in dots[:]:
            for p in players:
                if p.get("dead"):
                    continue
                if p["rect"].colliderect(dot):
                    dots.remove(dot)
                    collected_dots += 1
                    if snd_eat: snd_eat.play()
                    break

        # Режим монстров
        if monster_mode == "random" and collected_dots >= next_trigger:
            monster_mode = "chase"
            chase_start_time = time.time()
            next_trigger += MONSTER_TRIGGER_STEP
        elif monster_mode == "chase" and time.time() - chase_start_time > CHASE_TIME:
            monster_mode = "random"

        # Монстры
        for m in monsters:
            rect = m["rect"]
            cx, cy = rect.centerx // TILE, rect.centery // TILE
            m["cell"] = (cx, cy)
            if monster_mode == "chase":
                target = min(
                    (p for p in players if not p.get("dead")),
                    key=lambda p: math.hypot(p["rect"].centerx - rect.centerx, p["rect"].centery - rect.centery),
                    default=None
                )
                if target:
                    gx, gy = target["rect"].centerx // TILE, target["rect"].centery // TILE
                    if not m["path"] or (gx, gy) != m["path"][-1]:
                        path = bfs_path(maze, m["cell"], (gx, gy))
                        m["path"] = path[1:] if len(path) > 1 else []
                    if m["path"]:
                        nx, ny = m["path"][0]
                        tx, ty = nx*TILE + TILE//2, ny*TILE + TILE//2
                        dx, dy = tx - rect.centerx, ty - rect.centery
                        dist = math.hypot(dx, dy)
                        if dist < 2:
                            m["path"].pop(0)
                        else:
                            rect.x += MONSTER_SPEED * dx/dist
                            rect.y += MONSTER_SPEED * dy/dist
            else:
                if can_move(rect, m["dx"], m["dy"]):
                    rect.x += m["dx"]
                    rect.y += m["dy"]
                else:
                    m["dx"], m["dy"] = random_direction()

        process_bombs()

        # Столкновение
        dead_players = sum(1 for p in players if p.get("dead"))
        for m in monsters:
            for p in players:
                if p.get("dead"):
                    continue
                if m["rect"].colliderect(p["rect"]):
                    if snd_caught: snd_caught.play()
                    p["dead"] = True
                    dead_players += 1
                    p["color"] = GRAY
                    p["vx"], p["vy"] = 0, 0
                    msg = font.render(f"Игрок {'1' if players.index(p)==0 else '2'} погиб! Осталось {len(players) - dead_players}", True, WHITE)
                    screen.blit(msg, (150, HEIGHT//2))
                    pygame.display.flip()
                    pygame.time.wait(1000)

                    if dead_players >= len(players):
                        msg = font.render("Оба игрока мертвы! Нажми R для перезапуска.", True, WHITE)
                        screen.blit(msg, (100, HEIGHT//2 + 30))
                        pygame.display.flip()
                        pygame.time.wait(2000)
                        reset_game(player_count)

        # Отрисовка
        for w in walls:
            pygame.draw.rect(screen, BLUE, w)
        for d in dots:
            pygame.draw.rect(screen, WHITE, d)
        for m in monsters:
            color = RED if monster_mode == "chase" else (200, 50, 50)
            pygame.draw.rect(screen, color, m["rect"])
        for b in bombs:
            bx, by = b["pos"]
            if not b["exploded"]:
                pygame.draw.circle(screen, GRAY, (int(bx), int(by)), 6)
            else:
                pygame.draw.circle(screen, EXPLOSION_COLOR, (int(bx), int(by)), int(b["radius"]), 2)
                pygame.draw.circle(screen, ORANGE, (int(bx), int(by)), int(b["radius"] * 0.5))

        for p in players:
            draw_pacman(p)

        text = f"Счёт: {collected_dots}"
        if monster_mode == "chase":
            t = int(CHASE_TIME - (time.time() - chase_start_time))
            text += f" ⚠ Преследование: {t}s"
        screen.blit(font.render(text, True, WHITE), (10, 5))

        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()
