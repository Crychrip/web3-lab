package main

type MsgType uint8

const (
	MsgRequest MsgType = iota
	MsgPrePrepare
	MsgPrepare
	MsgCommit
)

type Message struct {
	Type     MsgType
	From     int
	View     int
	Seq      uint64
	Digest   [32]byte
	Cycle    TaskCycle
	ClientCh chan bool
}
