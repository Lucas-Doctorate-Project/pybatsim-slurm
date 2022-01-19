
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

    #Cmax = 9
    #Tmax = 3

    return M, N, K, c, p, b, d, env #, Cmax, Tmax

def test_luc2():
    N = 1
    M = 2
    K = 1

    p = [[1], [1]]
    c = [[1], [1]]
    b = [[1], [1]]
    d = [[1], [1]]
    env = [0]

    #Cmax = 9
    #Tmax = 3

    return M, N, K, c, p, b, d, env #, Cmax, Tmax

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

    #Cmax = 4
    #Tmax = 2

    return M, N, K, c, p, b, d, env #, Cmax, Tmax

def test_1_1():
    """
    To check if the solution will schedule based on the best << env processing time >>
    """

    desc = "To check if the solution will schedule based on the best << env processing time >>"
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

    #Cmax = 2
    #Tmax = 1

    return M, N, K, c, p, b, d, env #, Cmax, Tmax

def test_1_3():
    """
    To check if the solution will schedule based on the best << function processing time >>
    """

    desc = "To check if the solution will schedule based on the best << function processing time >>"
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

    #Cmax = 2
    #Tmax = 4

    return M, N, K, c, p, b, d, env #, Cmax, Tmax

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

    #Cmax = 2
    #Tmax = 4

    return M, N, K, c, p, b, d, env #, Cmax, Tmax

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

    #Cmax = 3
    #Tmax = 5

    return M, N, K, c, p, b, d, env #, Cmax, Tmax

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

    #Cmax = 5
    #Tmax = 3

    #Cmax, Tmax = compute_max_cmax_and_tmax(c, p, b, d)
    #print(Cmax, Tmax)
    
    return M, N, K, c, p, b, d, env #, Cmax, Tmax

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

    d =    [[1],
            [1],
            [1]]

    b =    [[1],
            [1],
            [1]]

    env =  [0, 0]

    #Cmax = 7
    #Tmax = 3

    #Cmax, Tmax = compute_max_cmax_and_tmax(c, p, b, d)
    #print(Cmax, Tmax)
    
    return M, N, K, c, p, b, d, env #, Cmax, Tmax

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

    d =    [[1],
            [1],
            [1]]

    b =    [[1],
            [1],
            [1]]

    env =  [0, 0]

    #Cmax = 3
    #Tmax = 7

    #Cmax, Tmax = compute_max_cmax_and_tmax(c, p, b, d)
    #print(Cmax, Tmax)
    
    return M, N, K, c, p, b, d, env #, Cmax, Tmax