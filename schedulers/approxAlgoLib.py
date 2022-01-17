from mip import Model, xsum, maximize, minimize, BINARY, CONTINUOUS
import numpy as np
import networkx as nx

def print_as_matrix(matrix):
    for line in matrix:
        print(line)
    return

def LP(Cmax, Tmax, M, N, K, c, p, d, b, env):
    try:
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
    except:
        return 1, 1, 1

def LP_minimum_cost(Cmax, Tmax, M, N, K, c, p, d, b, env):
    try:
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
    except:
        return 1, 1, 1

def LP_minimum_processing_time(Cmax, Tmax, M, N, K, c, p, d, b, env):
    try:
        m = Model("LP")
        
        x = [[m.add_var(var_type=CONTINUOUS) for j in range(N)] for i in range(M)]
        
        e = [[m.add_var(var_type=CONTINUOUS) for k in range(K)] for i in range(M)]
        
        m.objective = minimize(xsum(xsum(p[i][j]*x[i][j] for j in range(N)) for i in range(M)) + xsum(xsum(b[i][k]*e[i][k] for k in range(K)) for i in range(M)))

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
    except:
        return 1, 1, 1        

def to_integer_solution(x, M, N, K, c, p, d, b, env):

    try:
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

    except:
        return 1, 1

def compute_max_cmax_and_tmax(c, p, b, d):
    """
    Compute the max Cmax and Tmax allowed. Requirement: c,p,b,d should have the same dimention, then:
    Cmax = max(c) + max(d), per line 
    Tmax = max(p) + max(b), per line
    """
    cmax = 0
    tmax = 0
    # TODO To reverse the matrix to get the maximum per column and not per line
    # Here, iterating per line means iterating per machine and not per tasks.
    for i in range(0, len(c)):
        cmax += max(c[i]) + max(d[i])
        tmax += max(p[i]) + max(b[i])
    
    return cmax, tmax

def minimize_cmax_and_tmax_by_factor(Cmax, Tmax, M, N, K, c, p, d, b, env, factor):
    """
    Receive all parameters to compute the LP.
    It tries as far as possible to decrease Cmax and Tmax to find a better solution.
    It will descrease them as follows:
    new_cmax = Cmax - Cmax/factor
    new_tmax = Tmax - Tmax/factor
    """

    new_cmax = Cmax - Cmax/factor
    new_tmax = Tmax - Tmax/factor
    status_new, x_new, e_new = LP(new_cmax, new_tmax, M, N, K, c, p, d, b, env)
    print("Solution updated first", new_cmax, new_tmax)
    while(status_new == 0 and new_cmax > 0 and new_tmax > 0):
        print("Solution updated!", new_cmax, new_tmax)
        status, x, e = status_new, x_new, e_new
        Cmax, Tmax = new_cmax, new_tmax

        new_cmax = new_cmax - new_cmax/factor
        new_tmax = new_tmax - new_tmax/factor   
        status_new, x_new, e_new = LP(new_cmax, new_tmax, M, N, K, c, p, d, b, env)
    
    return status, x, e, Cmax, Tmax

def test_luc():
    """
    Test designed for Luc's presentation
    """

    desc = "Test designed for Luc's presentation"
    print("Test 0: ", desc)

    N = 7
    M = 3
    K = 1

    c =    [[3, 1, 1, 1, 1, 1, 1],
            [3, 1, 1, 1, 1, 1, 1],
            [3, 1, 1, 1, 1, 1, 1]]

    p =    [[3, 1, 1, 1, 1, 1, 1],
            [3, 1, 1, 1, 1, 1, 1],
            [3, 1, 1, 1, 1, 1, 1]]

    d =    [[0],
            [0],
            [0]]

    b =    [[0],
            [0],
            [0]]

    env =  [0, 0, 0, 0, 0, 0, 0]

    Cmax = 9
    Tmax = 3

    return M, N, K, c, p, b, d, env, Cmax, Tmax

def test_luc2():
    N = 1
    M = 2
    K = 1

    p = [[1], [1]]
    c = [[1], [1]]
    b = [[1], [1]]
    d = [[1], [1]]
    env = [0]

    Cmax = 9
    Tmax = 3

    return M, N, K, c, p, b, d, env, Cmax, Tmax

def test_1_0():
    """
    To check if the solution will schedule based on the best << env cost >>
    """

    desc = "To check if the solution will schedule based on the best << env cost >>"
    print("Test 1_0: ", desc)

    N = 1
    M = 3
    K = 1

    c = [[1], 
        [1], 
        [1]]

    p = [[1], 
        [1], 
        [1]]

    b = [[1], 
        [1], 
        [1]]

    d = [[2], 
        [3], 
        [1]]                

    env = [0, 0, 0]

    Cmax = 4
    Tmax = 2

    return M, N, K, c, p, b, d, env, Cmax, Tmax

def test_1_1():
    """
    To check if the solution will schedule based on the best << env consuming time >>
    """

    desc = "To check if the solution will schedule based on the best << env consuming time >>"
    print("Test 1_1: ", desc)

    N = 1
    M = 3
    K = 1

    c = [[1], 
        [1], 
        [1]]

    p = [[1], 
        [1], 
        [1]]

    b = [[2], 
        [3], 
        [1]]     
        
    d = [[1], 
        [1], 
        [1]]

    env = [0, 0, 0]

    Cmax = 2
    Tmax = 4

    return M, N, K, c, p, b, d, env, Cmax, Tmax

def test_1_3():
    """
    To check if the solution will schedule based on the best << function consuming time >>
    """

    desc = "To check if the solution will schedule based on the best << function consuming time >>"
    print("Test 1_1: ", desc)

    N = 1
    M = 3
    K = 1

    c = [[1], 
        [1], 
        [1]]

    p = [[2], 
        [3], 
        [1]]

    b = [[1], 
        [1], 
        [1]]     
        
    d = [[1], 
        [1], 
        [1]]

    env = [0, 0, 0]

    Cmax = 2
    Tmax = 4

    return M, N, K, c, p, b, d, env, Cmax, Tmax

def test_1_4():
    """
    To check if the solution will schedule based on the best << function cost >>
    """

    desc = "To check if the solution will schedule based on the best << function cost >>"
    print("Test 1_1: ", desc)

    N = 1
    M = 3
    K = 1

    c = [[2], 
        [3], 
        [1]]

    p = [[1], 
        [1], 
        [1]]

    b = [[1], 
        [1], 
        [1]]     
        
    d = [[1], 
        [1], 
        [1]]

    env = [0, 0, 0]

    Cmax = 2
    Tmax = 4

    return M, N, K, c, p, b, d, env, Cmax, Tmax

def test_2_0():
    """
    To check if the solution will schedule based on the best << env consuming time >>
    """

    desc = "To check if the solution will schedule based on the best << env consuming time >>"
    print("Test 2_0: ", desc)

    N = 2
    M = 3
    K = 1

    c =    [[1, 1],
            [1, 1],
            [1, 1]]

    p =    [[1, 1],
            [1, 1],
            [1, 1]]

    d =    [[1],
            [1],
            [1]]

    b =    [[3],
            [1],
            [2]]

    env =  [0, 0]

    Cmax = 6
    Tmax = 8

    return M, N, K, c, p, b, d, env, Cmax, Tmax

def test_2_1():
    """
    To check if the solution will schedule based on the best << env cost >>
    """

    desc = "To check if the solution will schedule based on the best << env cost >>"
    print("Test 2_0: ", desc)

    N = 2
    M = 3
    K = 1

    c =    [[1, 1],
            [1, 1],
            [1, 1]]

    p =    [[1, 1],
            [1, 1],
            [1, 1]]

    d =    [[3],
            [1],
            [2]]
            
    b =    [[1],
            [1],
            [1]]

    env =  [0, 0]

    Cmax = 4
    Tmax = 2

    #Cmax, Tmax = compute_max_cmax_and_tmax(c, p, b, d)
    print(Cmax, Tmax)
    
    return M, N, K, c, p, b, d, env, Cmax, Tmax

def test_2_3():
    """
    To check if the solution will schedule based on the best << env cost >>
    """

    desc = "To check if the solution will schedule based on the best << function cost >>"
    print("Test 2_0: ", desc)

    N = 2
    M = 3
    K = 1

    c =    [[3, 3],
            [1, 1],
            [2, 2]]

    p =    [[1, 1],
            [1, 1],
            [1, 1]]

    d =    [[1, 1],
            [1, 1],
            [1, 1]]
            
    b =    [[1, 1],
            [1, 1],
            [1, 1]]

    env =  [0, 0]

    Cmax = 4
    Tmax = 2

    #Cmax, Tmax = compute_max_cmax_and_tmax(c, p, b, d)
    print(Cmax, Tmax)
    
    return M, N, K, c, p, b, d, env, Cmax, Tmax

def test_2_4():
    """
    To check if the solution will schedule based on the best << function consumption time >>
    """

    desc = "To check if the solution will schedule based on the best << function consumption time >>"
    print("Test 2_0: ", desc)

    N = 2
    M = 3
    K = 1

    c =    [[1, 1],
            [1, 1],
            [1, 1]]

    p =    [[3, 3],
            [1, 1],
            [2, 2]]

    d =    [[1, 1],
            [1, 1],
            [1, 1]]
            
    b =    [[1, 1],
            [1, 1],
            [1, 1]]

    env =  [0, 0]

    Cmax = 4
    Tmax = 2

    #Cmax, Tmax = compute_max_cmax_and_tmax(c, p, b, d)
    print(Cmax, Tmax)
    
    return M, N, K, c, p, b, d, env, Cmax, Tmax

def get_cost(x, e, c, d):
    tcost = np.sum(x*c)
    ecost = np.sum(e*d)
    
    return tcost + ecost

def main():

    M, N, K, c, p, b, d, env, Cmax, Tmax = test_2_1()

    print("\nInputs: ")
    print("job costs: \n", c)
    print("job consuming time: \n", p)
    print("env costs: \n", d)
    print("env consuming time:: \n", b)
    print("env dependencies: \n", env)

    #status, x, e = LP(Cmax, Tmax, M, N, K, c, p, d, b, env)
    status, x, e = LP_minimum_cost(Cmax, Tmax, M, N, K, c, p, d, b, env)
    new_cmax = get_cost(x, e, c, d)
    
    print("\nFirst Step : ")
    print(str(np.round(x, 2)))
    x_a, e_a = to_integer_solution(x, M, N, K, c, p, d, b, env)
    print("\nIntegerized solution : ")
    print(x_a)
    
    status, x, e = LP_minimum_processing_time(new_cmax, Tmax, M, N, K, c, p, d, b, env)

    if(status == 1):
        print("Status: Failed to fing a solution (maybe TMAX and CMAX are too small).")
    else:
        print("\nLP solution : ")
        print(str(np.round(x, 2)))

        x_a, e_a = to_integer_solution(x, M, N, K, c, p, d, b, env)

        print("\nIntegerized solution : ")
        print(x_a)

    #convert_matrix_to_dictionary(x_a)

main()