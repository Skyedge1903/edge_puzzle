import numpy as np
import pandas as pd
from pulp import (
    LpProblem, LpVariable, LpMaximize,
    lpSum, LpContinuous, LpBinary,
    PULP_CBC_CMD
)
import time

# =========================
# Paramètres
# =========================
SIZE = 16
ROT = 4
TILES_CSV = "eternity2_256.csv"
OUT_CSV = "best_eternity2_solution.csv"

# Directions
N, E, S, W = 0, 1, 2, 3
DIRS = [(0,1),(1,0)]  # E, S

# =========================
# Chargement tuiles
# =========================
tiles = pd.read_csv(TILES_CSV, header=None).values.astype(int)
NTILES = len(tiles)

# Rotations
t_rot = np.zeros((NTILES*ROT,4),dtype=int)
for p in range(NTILES):
    for r in range(ROT):
        t_rot[p*ROT+r] = np.roll(tiles[p], -r)

# Couleurs distinctes
COLORS = sorted(set(t_rot.flatten()))
NC = len(COLORS)
color_index = {c:i for i,c in enumerate(COLORS)}

# =========================
# Indexation des arêtes
# =========================
edges = []
edge_id = {}

eid = 0
for i in range(SIZE):
    for j in range(SIZE):
        if j+1 < SIZE:
            edge_id[(i,j,E)] = eid
            edges.append((i,j,E))
            eid += 1
        if i+1 < SIZE:
            edge_id[(i,j,S)] = eid
            edges.append((i,j,S))
            eid += 1

NE = len(edges)
print(f"{NE} arêtes internes (score max = {NE})")

# =========================
# Modèle LP
# =========================
prob = LpProblem("Eternity2_EdgeColor_LP", LpMaximize)

# Variables pièces
x = {
    (i,j,p,r): LpVariable(f"x_{i}_{j}_{p}_{r}",0,1,LpBinary)
    for i in range(SIZE)
    for j in range(SIZE)
    for p in range(NTILES)
    for r in range(ROT)
}

# Variables couleurs d’arêtes
z = {
    (e,c): LpVariable(f"z_{e}_{c}",0,1,LpContinuous)
    for e in range(NE)
    for c in range(NC)
}

# Variables score
y = {
    e: LpVariable(f"y_{e}",0,1,LpContinuous)
    for e in range(NE)
}

# =========================
# Contraintes
# =========================
print("Création contraintes...")
t0 = time.time()

# Une pièce par case
for i in range(SIZE):
    for j in range(SIZE):
        prob += lpSum(x[i,j,p,r] for p in range(NTILES) for r in range(ROT)) == 1

# Chaque pièce utilisée une fois
for p in range(NTILES):
    prob += lpSum(x[i,j,p,r] for i in range(SIZE) for j in range(SIZE) for r in range(ROT)) == 1

# Une couleur par arête
for e in range(NE):
    prob += lpSum(z[e,c] for c in range(NC)) == 1

# Lien pièce → arête (ultra-local)
for i,j,d in edge_id:
    e = edge_id[(i,j,d)]

    if d == E:
        for p in range(NTILES):
            for r in range(ROT):
                c = color_index[t_rot[p*ROT+r][E]]
                prob += z[e,c] >= x[i,j,p,r]

        for p in range(NTILES):
            for r in range(ROT):
                c = color_index[t_rot[p*ROT+r][W]]
                prob += z[e,c] >= x[i,j+1,p,r]

    if d == S:
        for p in range(NTILES):
            for r in range(ROT):
                c = color_index[t_rot[p*ROT+r][S]]
                prob += z[e,c] >= x[i,j,p,r]

        for p in range(NTILES):
            for r in range(ROT):
                c = color_index[t_rot[p*ROT+r][N]]
                prob += z[e,c] >= x[i+1,j,p,r]

# Score
for e in range(NE):
    for c in range(NC):
        prob += y[e] <= z[e,c]

print(f"Contraintes créées en {time.time()-t0:.2f}s")

# =========================
# Objectif
# =========================
prob += lpSum(y[e] for e in range(NE))

# =========================
# Résolution
# =========================
solver = PULP_CBC_CMD(msg=1, threads=4, timeLimit=1800)
print("Résolution LP...")
t0 = time.time()
prob.solve(solver)
print(f"Terminé en {(time.time()-t0)/60:.2f} min")

# =========================
# Export CSV compatible
# =========================
with open(OUT_CSV,"w") as f:
    for i in range(SIZE):
        for j in range(SIZE):
            for p in range(NTILES):
                for r in range(ROT):
                    if x[i,j,p,r].varValue > 0.5:
                        f.write(f"{i},{j},{p+1},{r}\n")
                        break

print("Solution exportée :", OUT_CSV)
