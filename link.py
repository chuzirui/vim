#!/usr/bin/env python
# -*- coding: utf-8 -*-
class LinkedNode(object):
    def __init__(self, value):
        self.next = None
        self.value = value


def insert_linked(Head, Node):
    Node.next = Head.next
    Head.next = Node


def print_list(Head):
    while (Head):
        print (Head.value)
        Head = Head.next


def delete_node_list(Head, Node):
    while (Head):
        if (Head.next == Node):
            Head.next = Node.next
            return
        Head = Head.next


def reverse_list(Head):
    c2 = Head.next
    Head.next = None
    while (c2):
        c3 = c2.next
        c2.next = Head
        Head = c2
        c2 = c3

    return Head


n1 = LinkedNode(1)
n2 = LinkedNode(2)
n3 = LinkedNode(3)
n4 = LinkedNode(4)

head = n1

insert_linked(head, n2)
insert_linked(head, n3)
insert_linked(head, n4)
print_list(head)
head = reverse_list(head)
print_list(head)


