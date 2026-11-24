import math
L1,L,L2,L3,DX,N_RPM,FI0 = 20.,25.,50.,60.,20.,250.,90.
def state(fi):
    p=math.radians(fi)
    A=(0.,0.); C=(0.,-L); B=(L1*math.cos(p),L1*math.sin(p))
    q=(B[0]-C[0],B[1]-C[1]); h=math.hypot(*q)
    D=(C[0]+L2*q[0]/h,C[1]+L2*q[1]/h)
    E=(D[0]+math.sqrt(L3**2-D[1]**2),0.)
    X=(D[0]+DX/L3*(E[0]-D[0]),D[1]+DX/L3*(E[1]-D[1]))
    return A,B,C,D,E,X
def audit():
    for fi in range(361):
        A,B,C,D,E,X=state(fi)
        for a,b,length in ((A,B,L1),(A,C,L),(C,D,L2),(D,E,L3),(D,X,DX)):
            assert abs(math.dist(a,b)-length)<1e-8,(fi,length)
        assert abs(E[1])<1e-9
        assert abs((B[0]-C[0])*(D[1]-C[1])-(B[1]-C[1])*(D[0]-C[0]))<1e-8
    print("CALCULATION_ONLY_PASS")
if __name__=="__main__": audit()
