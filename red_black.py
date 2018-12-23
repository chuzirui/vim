"""An implementation of red-black trees, based on the description in
Introduction to Algorithms (Cormen, Leiserson, Rivest), Chapter 14.

Danny Yoo (dyoo@hkn.eecs.berkeley.edu)

Well, actually, direct copying is a more accurate
description... *grin* It's nice to see how well we can express this
implementation --- it's almost word-for-word identical with the
pseudocode in CLR.

I know I can make typos, so I'm stuffing this full with unit tests.
"""


"""Each node can be colored RED or BLACK."""
RED = "RED"
BLACK = "BLACK"



class NilNode(object):
    def __init__(self):
        self.color = BLACK

"""We define NIL to be the leaf sentinel of our tree."""
NIL = NilNode()



class Node(object):
    def __init__(self, key, color=RED, left=NIL, right=NIL, p=NIL):
        """Constructs a single node of the red-black tree.
        Key is the key that has an ordering.
        color is RED or BLACK.
        left and right are the left and right subtrees.
        p is the parent Node.
        """
        assert color in (RED, BLACK)
        self.color, self.key, self.left, self.right, self.p = (
            color, key, left, right, p)


class Tree(object):
    def __init__(self, root=NIL):
        self.root = root


def left_rotate(T, x):
    """Left-rotates node x on tree T.

               x
              / \
             a   y
                / \
               b   g

    mutates into:

               y
              / \
             x   g
            / \
           a   b

    Used for maintaining tree balance.
    """
    assert (x.right != NIL)
    y = x.right
    x.right = y.left
    if y.left != NIL:
        y.left.p = x
    y.p = x.p
    if x.p == NIL:
        T.root = y
    elif x == x.p.left:
        x.p.left = y
    else:
        x.p.right = y
    y.left = x
    x.p = y


def right_rotate(T, x):
    """Right-rotates node x on tree T.

               x
              / \
             y   g
            / \
           a   b

    mutates into:

               y
              / \
             a   x
                / \
               b   g

    Used for maintaining tree balance.
    """
    assert (x.left != NIL)
    y = x.left
    x.left = y.right
    if y.right != NIL:
        y.right.p = x
    y.p = x.p
    if x.p == NIL:
        T.root = y
    elif x == x.p.right:
        x.p.right = y
    else:
        x.p.left = y
    y.right = x
    x.p = y



def tree_insert(tree, z):
    """Inserts node 'z' into binary tree 'tree'."""
    y = NIL
    x = tree.root
    while x != NIL:
        y = x
        if z.key < x.key:
            x = x.left
        else:
            x = x.right
    z.p = y
    if y == NIL:
        tree.root = z
    elif z.key < y.key:
        y.left = z
    else:
        y.right = z
        

def rb_insert(tree, x):
    """Does an insertion of 'x' into the red-black tree 'tree'.  The
    algorithm here is a little subtle, but is explained in CLR."""
    tree_insert(tree, x)
    x.color = RED
    while x != tree.root and x.p.color == RED:
        if x.p == x.p.p.left:
            y = x.p.p.right
            if y.color == RED:
                x.p.color = BLACK
                y.color = BLACK
                x.p.p.color = RED
                x = x.p.p
            else:
                if x == x.p.right:
                    x = x.p
                    left_rotate(tree, x)
                x.p.color = BLACK
                x.p.p.color = RED
                right_rotate(tree, x.p.p)
        else:
            y = x.p.p.left
            if y.color == RED:
                x.p.color = BLACK
                y.color = BLACK
                x.p.p.color = RED
                x = x.p.p
            else:
                if x == x.p.left:
                    x = x.p
                    right_rotate(tree, x)
                x.p.color = BLACK
                x.p.p.color = RED
                left_rotate(tree, x.p.p)
    tree.root.color = BLACK


def tree_minimum(x):
    """Returns the minimal element of the subtree rooted at 'x'."""
    while x.left != NIL:
        x = x.left
    return x


def tree_maximum(x):
    """Returns the maximal element of the subtree rooted at 'x'."""
    while x.right != NIL:
        x = x.right
    return x


def tree_successor(x):
    """Returns the inorder successor of node 'x'."""
    if x.right != NIL:
        return tree_minimum(x.right)
    y = x.p
    while y != NIL and x == y.right:
        x = y
        y = y.p
    return y


def tree_predecessor(x):
    """Returns the inorder predecessor of node 'x'."""
    if x.left != NIL:
        return tree_maximum(x.left)
    y = x.p
    while y != NIL and x == y.left:
        x =y
        y = y.p
    return y


def tree_height(node):
    """Returns the height of a subtree rooted by node 'node'."""
    if node == NIL: return 0
    return max(1 + tree_height(node.left), 1 + tree_height(node.right))


def tree_count_internal(node):
    """Returns the number of internal nodes in the subtree rooted at 'node'."""
    if node == NIL: return 0
    return 1 + tree_count_internal(node.left) + tree_count_internal(node.right)



######################################################################
## Unit tests

import unittest
class RedBlackTest(unittest.TestCase):
    def setUp(self):
        pass


    def tearDown(self):
        pass


    def testRotationOneElementTree(self):
        """Checks to see that left and right rotation on one-element
        trees throws AssertionErrors."""
        tree = Tree()
        tree.root = Node(5)
        self.assertRaises(AssertionError, left_rotate, tree, tree.root)
        self.assertRaises(AssertionError, right_rotate, tree, tree.root)
        

    def testBinaryInsertion(self):
        """Checks that we get
             5
            / \
           3   7
          /   /
         1   6
        """
        one, three, five, six, seven = map(lambda x: Node(x),
                                           [1, 3, 5, 6, 7])
        tree = Tree()
        tree_insert(tree, five)
        tree_insert(tree, three)
        tree_insert(tree, seven)
        tree_insert(tree, one)
        tree_insert(tree, six)
        self.assertEquals(tree.root, five)
        self.assertEquals(tree.root.left, three)
        self.assertEquals(tree.root.left.left, one)
        self.assertEquals(tree.root.right, seven)
        self.assertEquals(tree.root.right.left, six)


    def testTreeInsertHundredElements(self):
        MAX = 100
        nodes = map(Node, range(MAX))
        tree = Tree()
        for n in nodes: tree_insert(tree, n)
        self.assertEquals(nodes[0], tree_minimum(tree.root))
        for i in range(MAX-1):
            self.assertEquals(nodes[i], tree_predecessor(nodes[i+1]))
        ## Worse case input to a binary tree should produce one long chain!
        self.assertEquals(MAX, tree_height(tree.root))
        

    def testRotationTwoElementTree(self):
        """Check to see that
             x
           /
          y

        transforms to
            y
             \
              x

        and back again.
        """
        tree = Tree()
        x = Node('x', 'BLACK')
        y = Node('y', 'RED', p=x)
        x.left = y
        tree.root = x
        right_rotate(tree, x)
        self.assertEquals(tree.root, y)
        self.assertEquals(tree.root.right, x)
        self.assertEquals(tree.root.left, NIL)
        self.assertEquals((tree.root.right.left, tree.root.right.right),
                          (NIL, NIL))

        left_rotate(tree, y)

        self.assertEquals(tree.root, x)
        self.assertEquals(tree.root.left, y)
        self.assertEquals(tree.root.right, NIL)
        self.assertEquals((tree.root.left.left, tree.root.left.right),
                          (NIL, NIL))


    def testRbInsertOneElement(self):
        tree = Tree()
        one = Node('1')
        rb_insert(tree, one)
        self.assertEquals(tree.root, one)
        self.assertEquals(tree.root.color, BLACK)


    def testRbInsertTwoElements(self):
        tree = Tree()
        nodes = map(Node, range(2))
        for n in nodes:
            rb_insert(tree, n)
        self.assertEquals(tree.root, nodes[0])
        self.assertEquals(tree.root.right, nodes[1])


    def testRbInsertThreeElements(self):
        """
        We expect to get:

          1b
         /  \
        0r  2r
        """
        tree = Tree()
        nodes = map(Node, range(3))
        for n in nodes:
            rb_insert(tree, n)
        self.assertEquals(tree.root, nodes[1])
        self.assertEquals(tree.root.left, nodes[0])
        self.assertEquals(tree.root.right, nodes[2])
        self.assertEquals([RED, BLACK, RED], map(lambda n: n.color,
                                                 nodes))
        self.assertEquals(nodes[0], tree_minimum(tree.root))
        self.assertEquals(nodes[1], tree_successor(tree_minimum(tree.root)))
        self.assertEquals(nodes[2], tree_successor
                          (tree_successor(tree_minimum(tree.root))))
        self.assertEquals(NIL,      tree_successor
                          (tree_successor(tree_successor
                                          (tree_minimum(tree.root)))))
        
        self.assertEquals(nodes[1], tree_predecessor(nodes[2]))
        self.assertEquals(nodes[0], tree_predecessor(nodes[1]))


    def testRbFourElements(self):
        """
          1b 
         /  \
        0b  2b 
              \
              3r
        """
        MAX = 4
        nodes = map(Node, range(MAX))
        tree = Tree()
        for n in nodes: rb_insert(tree, n)
        self.assertEquals(nodes[0], tree_minimum(tree.root))
        for i in range(MAX-1):
            self.assertEquals(nodes[i], tree_predecessor(nodes[i+1]))
        self.assertEquals(nodes[1], tree.root)
        self.assertEquals(nodes[0], tree.root.left)
        self.assertEquals(nodes[2], tree.root.right)
        self.assertEquals(nodes[3], tree.root.right.right)
        self.assertEquals([BLACK, BLACK, BLACK, RED],
                          map(lambda n: n.color, nodes))

        
    def isRbTreeHeightCorrect(self, tree):
        """By definition, the height of the resulting red-black tree
        is less than or equal to 2* lg(number_of_nodes + 1)."""
        def lg(x):
            import math
            return math.log(x) / math.log(2)
        return (tree_height(tree.root)
                <= 2 * lg(tree_count_internal(tree.root) + 1))
        

    def testRbHundredElements(self, MAX=100):
        nodes = map(Node, range(MAX))
        tree = Tree()
        for n in nodes: rb_insert(tree, n)
        self.assertEquals(nodes[0], tree_minimum(tree.root))
        for i in range(MAX-1):
            self.assertEquals(nodes[i], tree_predecessor(nodes[i+1]))
        def lg(x):
            import math
            return math.log(x) / math.log(2)
        ## By definition, the height of the resulting red-black tree
        ## is less than or equal to 2* lg(number_of_nodes + 1).
        self.assert_(self.isRbTreeHeightCorrect(tree))
        self.assertEquals(MAX, tree_count_internal(tree.root))


    def testRbThousandElements(self):
        self.testRbHundredElements(MAX=1000)


if __name__ == '__main__':
    unittest.main()
