"""Exact compressive jump states and closed triangular verification domains."""
import math
import numpy as np
from suites.analytical.momentum2d.suite import deck

G=9.80665
H1=.03
U1=1.7
DX=.025
NY=40
DY=.05

def reference(kind):
    if kind=='wall':
        lo,hi=H1*1.000001,1.
        for _ in range(150):
            mid=(lo+hi)/2
            residual=.5*G*(mid+H1)*(mid-H1)**2-H1*mid*U1**2
            if residual>0:hi=mid
            else:lo=mid
        h2=(lo+hi)/2;return h2,0.,-H1*U1/(h2-H1),0.
    ratio=.5*(math.sqrt(1+8*U1**2/(G*H1))-1);h2=H1*ratio
    boost=-.3 if kind=='moving-upstream' else 0.
    return h2,H1*U1/h2+boost,boost,.4 if kind=='oblique' else 0.

def make(kind,order,angle):
    h2,u2,s,vt=reference(kind);ul=U1+(s if kind!='wall' else 0.)
    nx=160 if kind=='wall' else 400;x0=-4. if kind=='wall' else -5.
    vertices=np.array([(x0+i*DX,j*DY-.1) for i in range(nx+1) for j in range(NY+1)])
    cells=[]
    for i in range(nx):
        for j in range(NY):
            a=i*(NY+1)+j;b=a+NY+1;cells.extend([(a,b,b+1),(a,b+1,a+1)])
    cells=np.array(cells);cx=vertices[cells,0].mean(1)
    theta=math.radians(angle);co,si=math.cos(theta),math.sin(theta)
    rotation=np.array([[co,-si],[si,co]]);xy=vertices@rotation.T
    h=np.where(cx<0,H1,h2) if kind!='wall' else np.full(len(cells),H1)
    u=np.where(cx<0,ul,u2) if kind!='wall' else np.full(len(cells),U1)
    uv=np.column_stack([u,np.full(len(cells),vt)])@rotation.T
    text=deck('lake',order,0).split('[2D_VERTICES]')[0]
    text=text.replace('END_TIME 00:00:20','END_TIME 00:00:01').replace('REPORT_STEP 00:00:01','REPORT_STEP 0:00:00.1').replace('MAX_TIMESTEP 0.25','MAX_TIMESTEP 0.01')
    text=text.replace('ROUTING_STEP 1','ROUTING_STEP 0.1')
    lines=[text,'[2D_VERTICES]']+[f'{x:.17g} {y:.17g} 0' for x,y in xy]
    lines+=['[2D_TRIANGLES]']+[f'{a} {b} {c} 1e-12 {v:.17g}' for (a,b,c),v in zip(cells,h)]
    lines+=['[2D_INITIAL_VELOCITY]']+[f'{i} {a:.17g} {b:.17g}' for i,(a,b) in enumerate(uv)]
    owners={}
    for c,ids in enumerate(cells):
        for edge in range(3):owners.setdefault(tuple(sorted((int(ids[(edge+1)%3]),int(ids[(edge+2)%3])))),[]).append((c,edge))
    lines+=['[2D_BOUNDARY_CONDITIONS]']
    for (a,b),slots in owners.items():
        if len(slots)!=1:continue
        c,edge=slots[0];lines.append(f'{c} {edge} WALL')
    return '\n'.join(lines)+'\n',dict(h2=h2,u2=u2,shock_speed=s,vt=vt,ul=ul,nx=nx,x0=x0,angle=angle,order=order,kind=kind),cx
