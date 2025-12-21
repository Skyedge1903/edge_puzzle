import os

import numpy as np
import pandas as pd
import multiprocessing
from numba import njit
import time

# ==============================
# Classe couleurs ANSI
# ==============================
class C:
    RESET   = "\033[0m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    CYAN    = "\033[36m"
    GRAY    = "\033[90m"
    BOLD    = "\033[1m"

# ==============================
# Paramètres globaux
# ==============================
SIZE = 16
ROT = 4
FIX_I, FIX_J = 8, 7
FIX_PIECE = 138
FIX_ROT = 0
NUM_CHAINS = 7
T0 = 20.0
T_MIN = 0.01
ALPHA = 0.99995
MAX_STEPS_WITHOUT_IMPROV = 30 * 10000
BOOST_MAX = 0.55
BOOST_MIN = 0.15
BORDER_PENALTY_WEIGHT = 1

DIRS = np.array([[-1,0],[0,1],[1,0],[0,-1]], dtype=np.int64)
OPP = np.array([2,3,0,1], dtype=np.int64)

# ==============================
# Chargement et rotations
# ==============================
def load_tiles(file_path="data/eternity2/eternity2_256.csv"):
    return pd.read_csv(file_path, header=None).values.astype(np.int16)

def precompute_rotations(tiles):
    N = len(tiles)
    S = N*ROT
    t_rot = np.zeros((S,4), dtype=np.int16)
    for p in range(N):
        for r in range(ROT):
            t_rot[p*ROT+r] = np.roll(tiles[p], -r)
    return t_rot, N, S

# ==============================
# Score compilé
# ==============================
@njit
def score_numba(board_p, board_r, t_rot):
    total = 0
    for i in range(SIZE):
        for j in range(SIZE):
            p = board_p[i,j]
            r = board_r[i,j]
            s = p*ROT+r
            t = t_rot[s]
            if i==0 and t[0]==-1: total += BORDER_PENALTY_WEIGHT
            if j==SIZE-1 and t[1]==-1: total += BORDER_PENALTY_WEIGHT
            if i==SIZE-1 and t[2]==-1: total += BORDER_PENALTY_WEIGHT
            if j==0 and t[3]==-1: total += BORDER_PENALTY_WEIGHT
            if i+1<SIZE:
                p2 = board_p[i+1,j]
                r2 = board_r[i+1,j]
                s2 = p2*ROT+r2
                if t[2]==t_rot[s2][0]: total += 1
            if j+1<SIZE:
                p2 = board_p[i,j+1]
                r2 = board_r[i,j+1]
                s2 = p2*ROT+r2
                if t[1]==t_rot[s2][3]: total += 1
    return total

# ==============================
# Optimisation locale compilée
# ==============================
@njit
def optimize_local(board_p, board_r, t_rot, positions):
    for idx in range(positions.shape[0]):
        i,j = positions[idx]
        if i==FIX_I and j==FIX_J:
            continue
        p = board_p[i,j]
        best_score = -1
        best_r = 0
        for r in range(ROT):
            board_r[i,j] = r
            s = p*ROT + r
            local = 0
            for d in range(4):
                di = DIRS[d,0]
                dj = DIRS[d,1]
                ni = i + di
                nj = j + dj
                if 0<=ni<SIZE and 0<=nj<SIZE:
                    p2 = board_p[ni,nj]
                    r2 = board_r[ni,nj]
                    s2 = p2*ROT+r2
                    if t_rot[s][d]==t_rot[s2][OPP[d]]:
                        local +=1
            t = t_rot[s]
            if i==0 and t[0]==-1: local += BORDER_PENALTY_WEIGHT
            if j==SIZE-1 and t[1]==-1: local += BORDER_PENALTY_WEIGHT
            if i==SIZE-1 and t[2]==-1: local += BORDER_PENALTY_WEIGHT
            if j==0 and t[3]==-1: local += BORDER_PENALTY_WEIGHT
            if local>best_score:
                best_score = local
                best_r = r
        board_r[i,j] = best_r

# ==============================
# Propose move compilé
# ==============================
@njit
def propose_move_numba(board_p, board_r):
    while True:
        i1,j1 = np.random.randint(0,SIZE), np.random.randint(0,SIZE)
        i2,j2 = np.random.randint(0,SIZE), np.random.randint(0,SIZE)
        if (i1,j1)!=(i2,j2) and (i1,j1)!=(FIX_I,FIX_J) and (i2,j2)!=(FIX_I,FIX_J):
            break
    new_p = board_p.copy()
    new_r = board_r.copy()
    new_p[i1,j1], new_p[i2,j2] = new_p[i2,j2], new_p[i1,j1]
    new_r[i1,j1], new_r[i2,j2] = new_r[i2,j2], new_r[i1,j1]
    affected = np.array([[i1,j1],[i2,j2]], dtype=np.int64)
    return new_p, new_r, affected

# ==============================
# Sauvegarde CSV
# ==============================
def save_board_csv(board_p, board_r, score):
    os.makedirs("solutions", exist_ok=True)  # Crée le dossier s'il n'existe pas
    filename = f"solutions/partial_solution_{score}.csv"
    with open(filename,'w') as f:
        for i in range(SIZE):
            for j in range(SIZE):
                p = board_p[i,j]
                r = board_r[i,j]
                orientation = ((4 - r) % 4 + 3) % 4
                f.write(f"{i},{j},{p+1},{orientation}\n")

# ==============================
# Simulated Annealing
# ==============================
def simulated_annealing_csv(seed, t_rot, N, global_best, global_lock):
    np.random.seed(seed)
    board_p = np.zeros((SIZE,SIZE), dtype=np.int16)
    board_r = np.zeros((SIZE,SIZE), dtype=np.int16)
    board_p[FIX_I,FIX_J] = FIX_PIECE
    board_r[FIX_I,FIX_J] = FIX_ROT

    available = [p for p in range(N) if p!=FIX_PIECE]
    idx = 0
    for i in range(SIZE):
        for j in range(SIZE):
            if (i,j)!=(FIX_I,FIX_J):
                board_p[i,j] = available[idx % len(available)]
                board_r[i,j] = np.random.randint(0,ROT)
                idx += 1

    current_score = score_numba(board_p, board_r, t_rot)
    best_p, best_r = board_p.copy(), board_r.copy()
    best_score = current_score
    T = T0
    steps_without_improv = 0
    max_possible_score = (SIZE*(SIZE-1)*2)+(4*SIZE-4)*BORDER_PENALTY_WEIGHT
    step = 0
    start_time = time.time()

    while True:
        new_p, new_r, affected = propose_move_numba(board_p, board_r)
        optimize_local(new_p, new_r, t_rot, affected)
        new_score = score_numba(new_p, new_r, t_rot)
        dS = new_score - current_score

        if dS > 0 or np.random.rand() < np.exp(dS / T):
            board_p, board_r = new_p, new_r
            current_score = new_score

            if current_score > best_score:
                best_p, best_r = board_p.copy(), board_r.copy()
                best_score = current_score
                steps_without_improv = 0
                save_board_csv(best_p, best_r, current_score)

                # Mise à jour du meilleur global
                with global_lock:
                    if current_score > global_best['score']:
                        global_best['score'] = current_score
                        global_best['seed'] = seed
                        global_best['time'] = time.time() - start_time
                        elapsed = global_best['time']
                        steps_per_sec = step / elapsed
                        console_log = (
                            f"{C.BOLD}{C.GREEN}| SEED {seed:<2} | SCORE {current_score:<5} | "
                            f"BEST SEED {seed:<2} | STEP {step:<7} | {steps_per_sec:>7.2f} steps/sec | "
                            f"TIME {elapsed:>7.1f}s |{C.RESET}"
                        )
                        print(console_log)

        else:
            steps_without_improv += 1

        T = max(T*ALPHA, T_MIN)
        step += 1

        if steps_without_improv > MAX_STEPS_WITHOUT_IMPROV:
            rand_factor = np.random.rand() # uniforme entre 0 et 1
            T = max(BOOST_MAX * rand_factor, BOOST_MIN)
            steps_without_improv = 0
            print(f"{C.BOLD}{C.YELLOW}| SEED {seed:<2} | TEMPERATURE BOOSTED TO {T:.4f} |{C.RESET}")
            save_board_csv(best_p, best_r, seed)

        if best_score == max_possible_score:
            print(f"{C.BOLD}{C.GREEN}| SEED {seed:<2} | SOLUTION FOUND! SCORE={best_score} |{C.RESET}")
            save_board_csv(best_p, best_r, seed)
            break

# ==============================
# Main parallèle
# ==============================
if __name__ == "__main__":
    tiles = load_tiles()
    t_rot, N, S = precompute_rotations(tiles)

    manager = multiprocessing.Manager()
    global_best = manager.dict({'score': -1, 'seed': -1, 'time': 0})
    global_lock = multiprocessing.Lock()

    processes = []
    for seed in range(NUM_CHAINS):
        p = multiprocessing.Process(target=simulated_annealing_csv,
                                    args=(seed, t_rot, N, global_best, global_lock))
        p.start()
        processes.append(p)
    for p in processes:
        p.join()

    print(f"{C.BOLD}{C.MAGENTA}| FINAL BEST SCORE {global_best['score']} by SEED {global_best['seed']} |{C.RESET}")