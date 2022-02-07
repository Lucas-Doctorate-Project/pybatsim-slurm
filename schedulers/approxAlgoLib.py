from hashlib import new
from mip import Model, xsum, maximize, minimize, BINARY, CONTINUOUS
import numpy as np
import networkx as nx
import approxAlgoLibTests
import matplotlib.pyplot as plt

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

def compute_max_cmax_and_tmax(c, p, b, d, K, M, N):
    """
    Compute the max Cmax and Tmax allowed. Requirement: c,p,b,d should have the same dimention, then:
    Cmax = max(c) + max(d), per line 
    Tmax = max(p) + max(b), per line
    """
    cmax = 0
    tmax = 0
    max_env_cost_per_machine = []
    max_env_processing_time_per_machine = []

    for i in range(0, K):
        max_env_cost_per_machine.append(max(map(lambda x: x[i], d)))
        max_env_processing_time_per_machine.append(max(map(lambda x: x[i], b)))

    max_function_cost_per_machine = []
    max_function_processing_time_per_machine = []
    for i in range(0, N):
        max_function_cost_per_machine.append(max(map(lambda x: x[i], c)))
        max_function_processing_time_per_machine.append(max(map(lambda x: x[i], p)))
    
    cmax = M * sum(max_env_cost_per_machine) + sum(max_function_cost_per_machine)
    tmax = M * sum(max_env_processing_time_per_machine) + sum(max_function_processing_time_per_machine)

    return cmax, tmax

def minimize_cmax_and_tmax_by_factor_new(Cmax, Tmax, M, N, K, c, p, d, b, env, factor):
    """
    Receive all parameters to compute the LP.
    It tries as far as possible to decrease Cmax and Tmax to find a better solution.
    It will descrease them as follows:
    new_cmax = Cmax - Cmax/factor
    new_tmax = Tmax - Tmax/factor
    """
    new_tmax = Tmax
    new_cmax = Cmax
    Cmax, Tmax = 0, 0

    # Intialize
    status_new, x_new, e_new = LP(Cmax, Tmax, M, N, K, c, p, d, b, env)

    while(new_cmax != Cmax or new_tmax != Tmax):
        # Try to move Tmax
        status, x, e = status_new, x_new, e_new
        Tmax = int(new_tmax)

        new_tmax = int(new_tmax - new_tmax/factor)
        status_new, x_new, e_new = LP(Cmax, new_tmax, M, N, K, c, p, d, b, env)  

        # No solution, revert to previous solution
        if status_new != 0 :
            status_new, x_new, e_new == status, x, e
            new_tmax = int(Tmax)
        
        # Try to move Cmax
        status, x, e = status_new, x_new, e_new
        Cmax = int(new_cmax)

        new_cmax = int(new_cmax - new_cmax/factor)
        status_new, x_new, e_new = LP(new_cmax, Tmax, M, N, K, c, p, d, b, env)
        
        # No solution, revert to previous solution
        if status_new != 0 :
            status_new, x_new, e_new == status, x, e
            new_cmax = int(Cmax)

    return status, x, e, Cmax, Tmax

def minimize_cmax_and_tmax_by_factor_direct(Cmax, Tmax, M, N, K, c, p, d, b, env, factor):
    """
    Receive all parameters to compute the LP.
    It tries as far as possible to decrease Cmax and Tmax to find a better solution.
    It will descrease them as follows:
    new_cmax = Cmax - Cmax/factor
    new_tmax = Tmax - Tmax/factor
    """
    print("------------------------- minimize_cmax_and_tmax_by_factor: ", factor)
    new_tmax = Tmax - Tmax/factor
    status_new, x_new, e_new = LP(Cmax, new_tmax, M, N, K, c, p, d, b, env)
    while(status_new == 0 and new_tmax > 0):
        status, x, e = status_new, x_new, e_new
        Tmax = int(new_tmax)

        new_tmax = int(new_tmax - new_tmax/factor)   
        status_new, x_new, e_new = LP(Cmax, new_tmax, M, N, K, c, p, d, b, env)

    new_cmax = Cmax - Cmax/factor
    status_new, x_new, e_new = LP(new_cmax, Tmax, M, N, K, c, p, d, b, env)
    while(status_new == 0 and new_cmax > 0):
        status, x, e = status_new, x_new, e_new
        Cmax = int(new_cmax)

        new_cmax = int(new_cmax - new_cmax/factor)
        status_new, x_new, e_new = LP(new_cmax, Tmax, M, N, K, c, p, d, b, env)
    return status, x, e, Cmax, Tmax

def minimize_cmax_and_tmax_by_factor_cmax(Cmax, Tmax, M, N, K, c, p, d, b, env, factor):
    # Iterative Binary Search Function
    # It returns index of x in given array arr if present,
    # else returns -1
    low_cmax = 0
    high_cmax = Cmax#len(arr) - 1
    mid_cmax = 0
    print("Starting binary search", low_cmax, mid_cmax, high_cmax, abs(high_cmax - low_cmax))
    print("e ai?: ", abs(high_cmax - low_cmax) < 0.001)
    while (low_cmax <= high_cmax and int(abs(high_cmax - low_cmax)) >= 10):
        print("e ai?: ", round(abs(high_cmax - low_cmax),2) >= 0.001)
        print("Entrou", low_cmax, mid_cmax, high_cmax, abs(high_cmax - low_cmax))
        mid_cmax = round((high_cmax + low_cmax) / 2,2)
        print("Aqui")
        status_new, x_new, e_new = LP(mid_cmax, Tmax, M, N, K, c, p, d, b, env)
        
        print("status_new: ", status_new, mid_cmax)
        # If x is greater, ignore left half
        if status_new == 0:
            print("Update high_cmax")
            high_cmax = mid_cmax
        # No solution, revert to previous solution
        else:
            low_cmax = mid_cmax

        print("Going to restart the loop: ", low_cmax, mid_cmax, high_cmax, round(abs(high_cmax - low_cmax),2))
    print("Got out of the loop", low_cmax, mid_cmax, high_cmax)

    # If we reach here, then the element was not present
    if (status_new == 0):
        return status_new, x_new, e_new, high_cmax, Tmax
    else:
        return 1, x_new, e_new, mid_cmax, Tmax

def get_solution_cost(x, e, M, N, K, c, p, d, b):
    
    return int(np.sum(x * c) + np.sum(e * d))

def get_solution_makespan(x, e, M, N, K, c, p, d, b):
    x_time = x * p
    e_time = e * b

    return int(max([np.sum(x_time[m]) + np.sum(e_time[m]) for m in range(M)]))

def find_Tmin(Cmax, Tmax, M, N, K, c, p, d, b, env):#, factor):

    low_tmax = 0
    high_tmax = Tmax
    mid_tmax = 0

    iterations = 0

    #while (low_tmax <= high_tmax and int(abs(high_tmax - low_tmax)) >= 10):
    while (low_tmax + 1 < high_tmax and iterations < 10):
        mid_tmax = round((high_tmax + low_tmax) / 2, 2)
        status_tmax, x_new, e_new = LP(Cmax, mid_tmax, M, N, K, c, p, d, b, env)
        
        # If x is greater, ignore left half
        if status_tmax == 0:
            print("Update high_tmax")
            high_tmax = mid_tmax

        # No solution, revert to previous solution
        else:
            low_tmax = mid_tmax
        
        iterations += 1
    
    return high_tmax

#def minimize_cmax_and_tmax_by_factor(Cmax, Tmax, x, e, M, N, K, c, p, d, b, env):#, factor):
def minimize_cmax_and_tmax(Cmax, Tmax, M, N, K, c, p, d, b, env):#, factor):
    # Initialization
    low_tmax = 0
    high_tmax = Tmax
    mid_tmax = 0
    iterations = 0
    
    new_cost = Cmax
    new_makespan = Tmax
    
    list_of_solution = []
    list_of_cmax_used = []
    list_of_tmax_used = []

    list_of_cmax_lp = []
    list_of_tmax_lp = []

    list_of_valid_cmax = []
    list_of_valid_tmax = []

    # Compute intial solution with the initial Cmax and Tmax
    
    #status_valid, x_valid, e_valid = 0, x, e
    status_tmax, x_new, e_new = LP(Cmax, Tmax, M, N, K, c, p, d, b, env)
    status_valid, x_valid, e_valid = status_tmax, x_new, e_new
    
    cost_lp = get_solution_cost(x_new, e_new, M, N, K, c, p, d, b)
    makespan_lp = get_solution_makespan(x_new, e_new, M, N, K, c, p, d, b)

    list_of_cmax_lp.append(cost_lp)
    list_of_tmax_lp.append(makespan_lp)
    
    # Compute the current value of cost and makespan with the initial solution
    x_valid, e_valid = to_integer_solution(x_new, M, N, K, c, p, d, b, env)
    new_cost = get_solution_cost(x_valid, e_valid, M, N, K, c, p, d, b)
    new_makespan = get_solution_makespan(x_valid, e_valid, M, N, K, c, p, d, b)
    
    # Save Cmax and Tmax used
    list_of_cmax_used.append(Cmax)
    list_of_tmax_used.append(Tmax)

    # Save valid solutions
    list_of_solution.append([Cmax, Tmax, x_valid, e_valid])
    list_of_valid_cmax.append(new_cost)
    list_of_valid_tmax.append(new_makespan)

    while (low_tmax <= high_tmax and iterations < 10):
        mid_tmax = int((high_tmax + low_tmax) / 2)
        status_tmax, x_new, e_new = LP(Cmax, mid_tmax, M, N, K, c, p, d, b, env)
        
        # If x is greater, ignore left half
        if status_tmax == 0:
            high_tmax = mid_tmax
            
            cost_lp = get_solution_cost(x_new, e_new, M, N, K, c, p, d, b)
            makespan_lp = get_solution_makespan(x_new, e_new, M, N, K, c, p, d, b)
            
            list_of_cmax_lp.append(cost_lp)
            list_of_tmax_lp.append(makespan_lp)

            x_valid, e_valid = to_integer_solution(x_new, M, N, K, c, p, d, b, env)
            status_valid  = status_tmax

            new_cost = get_solution_cost(x_valid, e_valid, M, N, K, c, p, d, b)
            new_makespan = get_solution_makespan(x_valid, e_valid, M, N, K, c, p, d, b)

            # Please, notice that new_makespan <= 3*high_tmax, so we can not
            # update high_tmax with new_makespan.

            list_of_cmax_used.append(Cmax)
            list_of_tmax_used.append(mid_tmax)

            list_of_solution.append([new_cost, new_makespan, x_valid, e_valid])
            list_of_valid_cmax.append(new_cost)
            list_of_valid_tmax.append(new_makespan)
            
        # No solution, revert to previous solution
        else:
            low_tmax = mid_tmax

        iterations += 1
    return status_valid, x_valid, e_valid, new_cost, new_makespan, list_of_valid_cmax, list_of_valid_tmax, list_of_cmax_used, list_of_tmax_used, list_of_cmax_lp, list_of_tmax_lp

def get_cost(x, e, c, d):
    tcost = np.sum(x*c)
    ecost = np.sum(e*d)
    
    return tcost + ecost

def main():

    M, N, K, c, p, b, d, env = approxAlgoLibTests.test_1_1()
    print("N",N)
    Cmax, Tmax = compute_max_cmax_and_tmax(c, p, b, d, K, M, N)

    print("\nInputs: ")
    print("job costs: \n", c)
    print("job processing time: \n", p)
    print("env costs: \n", d)
    print("env processing time: \n", b)
    print("env dependencies: \n", env)
    print("Cmax: ", Cmax)
    print("Tmax: ", Tmax)

    status, x, e = LP(Cmax, Tmax, M, N, K, c, p, d, b, env)

    if(status == 1):
        print("Status: Failed to find a solution.")
    else:
        print("\nLP solution : ")
        print(str(np.round(x, 2)))

        x_a, e_a = to_integer_solution(x, M, N, K, c, p, d, b, env)

        print("\nIntegerized solution : ")
        print(x_a)

    #convert_matrix_to_dictionary(x_a)

main()