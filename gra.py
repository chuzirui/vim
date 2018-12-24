#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
sys.setrecursionlimit(10000000)

class node(object):
     def __init__(self,color,size=1):
             self.color = color
             self.size = size
             self.empty= 1

gra = [
    [node("BLACK"),node("BLACK"),node("Yellow"),node("Yellow"),node("Yellow"),node("RED")],
    [node("BLACK"),node("BLACK"),node("BLACK"),node("BLACK"),node("Yellow"),node("Yellow")],
    [node("RED"),node("RED"),node("BLACK"),node("RED"),node("RED"),node("Yellow")]
    ]
class step(object):
    def __init__(self,x,y):
        self.x = x
        self.y = y

step_array = [step(-1,0), step(0,-1),step(1,0),step(0,1)]

def coverage(x,y):
    gra[x][y].empty = 0
    sum = 0
    for i in range(0,4):
        xplus = x + step_array[i].x
        yplus = y + step_array[i].y
        if xplus >=0 and yplus>=0 and xplus<3 and yplus<6:
            if gra[x][y].color == gra[xplus][yplus].color and gra[xplus][yplus].empty == 1:
                sum = sum + coverage(xplus,yplus)
    gra[x][y].size = gra[x][y].size + sum

    print ("x:",x, "y:",y, "cov", gra[x][y].size)
    return gra[x][y].size

max_c = 0
for k in range(0,3):
    for l in range(0,6):
        cov = coverage(k,l)
        if cov > max_c:
            max_c = cov

print (max_c)

