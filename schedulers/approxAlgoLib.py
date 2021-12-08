from mip import Model, xsum, maximize, minimize, BINARY, CONTINUOUS
import numpy as np
import networkx as nx

def LP(Cmax, Tmax, M, N, K, c, p, d, b, env):
    
    m = Model("LP")
    
    x = [[m.add_var(var_type=CONTINUOUS) for j in range(N)] for i in range(M)]
    
    e = [[m.add_var(var_type=CONTINUOUS) for k in range(K)] for i in range(M)]
    
    m.objective = minimize(xsum(xsum(c[i][j]*x[i][j] for j in range(N)) for i in range(M)) + xsum(xsum(d[i][k]*e[i][k] for k in range(K)) for i in range(M)))

    # Add constraints
    m += xsum(xsum(c[i][j]*x[i][j] for j in range(N)) for i in range(M)) + xsum(xsum(d[i][k]*e[i][k] for k in range(K)) for i in range(M)) <= Cmax

    for j in range(0, N):
        m += xsum(x[i][j] for i in range(M)) == 1

    for i in range(0, M):
        m += xsum(p[i][j]*x[i][j] for j in range(N)) + xsum(b[i][k]*e[i][k] for k in range(K)) <= Tmax
        
    for i in range(0, M):
        for j in range(0, N):
            m += x[i][j] <= e[i][env[j]]
            
    for k in range(0, K):
        for j in range(0, N):
            m += e[i][k] <= 1

    m.verbose = 0
    status = m.optimize()
    
    if(status.value == 0):
        out = np.array([[float(x[i][j].x) for j in range(N)] for i in range(M)])
    else:
        out = 0
    
    if(status.value == 0):
        out_e = np.array([[float(e[i][k].x) for k in range(K)] for i in range(M)])
    else:
        out_e = 0
    
    return status.value, out, out_e

def to_integer_solution(x, M, N, K, c, p, d, b, env):

    #if the solution given is already integer, assign the environments correctly and return
    if np.all([[not (j%1) for j in i]for i in x]):
        e = np.zeros((M, K))
        for m in range(M):
            for t in range(N):
                if x[m][t] == 1 and e[m][env[t]] == 0:
                    e[m][env[t]] = 1
        return x, e

    #k is a list of the number of sub-machines for each machine
    #k_inv if we align every sub-machine, k_inv gives us for each sub-machine to what machine it correspond
    k = []
    k_inv = []
    count = 0
    for i in range(M):
        k.append(int(np.ceil(np.sum(x[i]))))
        for j in range(k[i]):
            k_inv.append(count)  
        count = count + 1

    #number of sub-machines
    subM = int(np.sum(k))

    #
    bip = np.zeros((subM, N))

    #networkx bipartite graph
    B = nx.Graph()
    B.add_nodes_from(range(subM), bipartite=0)
    B.add_nodes_from(range(subM, subM + N), bipartite=1)

    #pour chaque machine
    for i in range(M):
        #subi the index of the 1st sub-machine of machine i
        subi = int(sum(k[:i]))
        #we order the tasks for machine i by decreasing processing times
        ordered_pi = sorted([[(p[i][j]+b[i][env[j]])*np.ceil(x[i][j]), j] for j in range(N)], reverse=True, key=lambda x: x[0])

        #take the first task
        count = 0
        e = ordered_pi[count]
        
        offset = 0

        #setting up the edges of the bipartite graph, like in 1st figure of page 16
        while count <= len(ordered_pi)-1 and ordered_pi[count][0] != 0:
            e = ordered_pi[count]
            filler = 0
            if np.sum(bip[subi + offset]) + x[i][e[1]] >= 1:
                filler = 1 - np.sum(bip[subi + offset])
                bip[subi + offset][e[1]] = filler
                B.add_edge(subi + offset, subM + e[1], weight = x[i][e[1]])
                offset = offset + 1
            
            if x[i][e[1]] - filler > 0.001:
                bip[subi + offset][e[1]] = bip[subi + offset][e[1]] + x[i][e[1]] - filler
                B.add_edge(subi + offset, subM + e[1], weight = x[i][e[1]])
            
            count = count + 1

    #cleaning the edges that are too small due to numerical errors, and the nodes that are not connected
    to_remove = [(a,b) for a, b, attrs in B.edges(data=True) if attrs["weight"] <= 0.00001]
    B.remove_edges_from(to_remove)
    B.remove_nodes_from(list(nx.isolates(B)))

    top_nodes = {n for n, d in B.nodes(data=True) if d["bipartite"] == 1}

    #minimum weight full matching, see figure 2 of page 16
    match = nx.algorithms.bipartite.matching.minimum_weight_full_matching(B, top_nodes)

    #formating the solution
    out = np.zeros((M, N))
    out_e = np.zeros((M, K))
    
    for i, m in enumerate(k_inv):
        try:
            t = match[i] - subM
            out[m][t] = 1
            if out_e[m][env[t]] == 0:
                out_e[m][env[t]] = 1
        except:
            pass
    
    return out, out_e

"""
def convert_matrix_to_dictionary(allocation_matrix):
    print("Allocation matrix: \n", allocation_matrix)

    print("Dimension", allocation_matrix.shape[0])

    # Initialize all lists in allocation_dictionary
    allocation_dictionary = {}
    for index_line in range (0, allocation_matrix.shape[0]):
        allocation_dictionary[index_line] = []

    # Assuming that line is machine
    for index_line in range (0, allocation_matrix.shape[0]):
        print(index_line)
        for index_column in range (0, allocation_matrix.shape[1]):
            #print(index_column)
            if allocation_matrix[index_line][index_column] == 1:
                allocation_dictionary[index_line].append(index_column)

    print("Allocation dict: ", allocation_dictionary)
"""

def main():

    print("First Part")

    N = 7;
    M = 3;
    K = 1;

    c =    [[3, 1, 1, 1, 1, 1, 1],
            [3, 1, 1, 1, 1, 1, 1],
            [3, 1, 1, 1, 1, 1, 1]];

    p =    [[3, 1, 1, 1, 1, 1, 1],
            [3, 1, 1, 1, 1, 1, 1],
            [3, 1, 1, 1, 1, 1, 1]];

    d =    [[0, 0],
            [0, 0],
            [0, 0]];

    b =    [[0, 0],
            [0, 0],
            [0, 0]];

    env =  [0, 0, 0, 0, 0, 0, 0];

    Cmax = 9
    Tmax = 3

    status, x, e = LP(Cmax, Tmax, M, N, K, c, p, d, b, env)
    print("LP solution : ")
    print(str(np.round(x, 2)))

    print("Second part")

    x_a, e_a = to_integer_solution(x, M, N, K, c, p, d, b, env)

    print("LP solution : ")
    print(str(np.round(x, 2)))
    print("Integerized solution : ")
    print(x_a)

    #convert_matrix_to_dictionary(x_a)

main()