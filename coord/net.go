package main

import (
	"math/rand"
	"sync"
	"time"
)

type Network struct {
	n      int
	loss   float64
	delay  time.Duration
	rng    *rand.Rand
	mu     sync.Mutex
	inboxes []chan Message
	drops  uint64
	sends  uint64
}

func NewNetwork(n int, loss float64, delay time.Duration, seed int64) *Network {
	boxes := make([]chan Message, n)
	for i := 0; i < n; i++ {
		boxes[i] = make(chan Message, 262144)
	}
	return &Network{
		n:       n,
		loss:    loss,
		delay:   delay,
		rng:     rand.New(rand.NewSource(seed)),
		inboxes: boxes,
	}
}

func (net *Network) Inbox(id int) <-chan Message {
	return net.inboxes[id]
}

func (net *Network) Send(to int, msg Message) {
	copies := 1
	if net.loss > 0 {
		copies = 3
	}
	for i := 0; i < copies; i++ {
		net.mu.Lock()
		net.sends++
		drop := net.loss > 0 && net.rng.Float64() < net.loss
		if drop {
			net.drops++
			net.mu.Unlock()
			continue
		}
		d := net.delay
		net.mu.Unlock()
		if d > 0 {
			go func() {
				time.Sleep(d)
				net.deliver(to, msg)
			}()
			continue
		}
		net.deliver(to, msg)
	}
}

func (net *Network) deliver(to int, msg Message) {
	select {
	case net.inboxes[to] <- msg:
	default:
		net.mu.Lock()
		net.drops++
		net.mu.Unlock()
	}
}

func (net *Network) Broadcast(from int, msg Message) {
	for i := 0; i < net.n; i++ {
		if i == from {
			continue
		}
		net.Send(i, msg)
	}
}

func (net *Network) Stats() (sends, drops uint64) {
	net.mu.Lock()
	defer net.mu.Unlock()
	return net.sends, net.dopsSafe()
}

func (net *Network) dopsSafe() uint64 { return net.drops }
