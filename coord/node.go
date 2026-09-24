package main

import (
	"sync"
)

type Node struct {
	id        int
	n         int
	f         int
	byzantine bool
	net       *Network

	mu        sync.Mutex
	view      int
	seq       uint64
	ledger    Ledger
	preprep   map[uint64][32]byte
	prepares  map[uint64]map[int][32]byte
	commits   map[uint64]map[int][32]byte
	cycles    map[uint64]TaskCycle
	executed  map[uint64]bool
	prepared  map[uint64]bool
	waiting   map[uint64]chan bool
	seenOrder map[uint64]bool
}

func NewNode(id, n, f int, byzantine bool, net *Network) *Node {
	return &Node{
		id:        id,
		n:         n,
		f:         f,
		byzantine: byzantine,
		net:       net,
		preprep:   map[uint64][32]byte{},
		prepares:  map[uint64]map[int][32]byte{},
		commits:   map[uint64]map[int][32]byte{},
		cycles:    map[uint64]TaskCycle{},
		executed:  map[uint64]bool{},
		prepared:  map[uint64]bool{},
		waiting:   map[uint64]chan bool{},
		seenOrder: map[uint64]bool{},
	}
}

func (nd *Node) primary() int { return nd.view % nd.n }

func (nd *Node) quorum() int { return 2*nd.f + 1 }

func (nd *Node) Run() {
	for msg := range nd.net.Inbox(nd.id) {
		if nd.byzantine {
			continue
		}
		switch msg.Type {
		case MsgRequest:
			nd.onRequest(msg)
		case MsgPrePrepare:
			nd.onPrePrepare(msg)
		case MsgPrepare:
			nd.onPrepare(msg)
		case MsgCommit:
			nd.onCommit(msg)
		}
	}
}

func (nd *Node) Submit(cycle TaskCycle, done chan bool) {
	nd.mu.Lock()
	nd.view = 0
	nd.mu.Unlock()
	nd.net.Send(nd.primary(), Message{Type: MsgRequest, From: nd.id, Cycle: cycle, ClientCh: done})
}

func (nd *Node) onRequest(msg Message) {
	nd.mu.Lock()
	if nd.id != nd.primary() {
		nd.mu.Unlock()
		return
	}
	if nd.seenOrder[msg.Cycle.OrderID] {
		nd.mu.Unlock()
		return
	}
	nd.seenOrder[msg.Cycle.OrderID] = true
	nd.seq++
	seq := nd.seq
	d := msg.Cycle.Digest()
	nd.preprep[seq] = d
	nd.cycles[seq] = msg.Cycle
	if msg.ClientCh != nil {
		nd.waiting[seq] = msg.ClientCh
	}
	out := Message{Type: MsgPrePrepare, From: nd.id, View: nd.view, Seq: seq, Digest: d, Cycle: msg.Cycle}
	nd.mu.Unlock()
	nd.net.Broadcast(nd.id, out)
	nd.onPrePrepare(out) // primary also prepares
}

func (nd *Node) onPrePrepare(msg Message) {
	nd.mu.Lock()
	if _, ok := nd.preprep[msg.Seq]; !ok {
		nd.preprep[msg.Seq] = msg.Digest
		nd.cycles[msg.Seq] = msg.Cycle
	}
	if nd.prepares[msg.Seq] == nil {
		nd.prepares[msg.Seq] = map[int][32]byte{}
	}
	nd.prepares[msg.Seq][nd.id] = msg.Digest
	view := nd.view
	nd.mu.Unlock()
	nd.net.Broadcast(nd.id, Message{Type: MsgPrepare, From: nd.id, View: view, Seq: msg.Seq, Digest: msg.Digest})
	nd.maybePrepare(msg.Seq)
}

func (nd *Node) onPrepare(msg Message) {
	nd.mu.Lock()
	if nd.prepares[msg.Seq] == nil {
		nd.prepares[msg.Seq] = map[int][32]byte{}
	}
	nd.prepares[msg.Seq][msg.From] = msg.Digest
	nd.mu.Unlock()
	nd.maybePrepare(msg.Seq)
}

func (nd *Node) maybePrepare(seq uint64) {
	nd.mu.Lock()
	if nd.prepared[seq] {
		nd.mu.Unlock()
		return
	}
	digest, ok := nd.preprep[seq]
	if !ok {
		nd.mu.Unlock()
		return
	}
	count := 0
	for _, d := range nd.prepares[seq] {
		if d == digest {
			count++
		}
	}
	if count < nd.quorum() {
		nd.mu.Unlock()
		return
	}
	nd.prepared[seq] = true
	if nd.commits[seq] == nil {
		nd.commits[seq] = map[int][32]byte{}
	}
	nd.commits[seq][nd.id] = digest
	view := nd.view
	nd.mu.Unlock()
	nd.net.Broadcast(nd.id, Message{Type: MsgCommit, From: nd.id, View: view, Seq: seq, Digest: digest})
	nd.maybeCommit(seq)
}

func (nd *Node) onCommit(msg Message) {
	nd.mu.Lock()
	if nd.commits[msg.Seq] == nil {
		nd.commits[msg.Seq] = map[int][32]byte{}
	}
	nd.commits[msg.Seq][msg.From] = msg.Digest
	nd.mu.Unlock()
	nd.maybeCommit(msg.Seq)
}

func (nd *Node) maybeCommit(seq uint64) {
	nd.mu.Lock()
	if nd.executed[seq] {
		nd.mu.Unlock()
		return
	}
	digest, ok := nd.preprep[seq]
	if !ok || !nd.prepared[seq] {
		nd.mu.Unlock()
		return
	}
	count := 0
	for _, d := range nd.commits[seq] {
		if d == digest {
			count++
		}
	}
	if count < nd.quorum() {
		nd.mu.Unlock()
		return
	}
	cycle := nd.cycles[seq]
	nd.ledger.Cycles = append(nd.ledger.Cycles, cycle)
	nd.executed[seq] = true
	wait := nd.waiting[seq]
	nd.mu.Unlock()
	if wait != nil {
		select {
		case wait <- true:
		default:
		}
	}
}

func (nd *Node) Snapshot() (int, string) {
	nd.mu.Lock()
	defer nd.mu.Unlock()
	return len(nd.ledger.Cycles), nd.ledger.HashHex()
}
