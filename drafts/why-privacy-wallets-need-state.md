# Why a Privacy Wallet Needs a Memory

Draft — Alex Newman · October 25, 2026

*Two promises every wallet likes to make, "restore from your twelve words" and "nobody can see who paid you", cannot both be kept on a phone. Winnow keeps the second and says so about the first. Here is why, and what a Bitcoin peer could do about it.*

Winnow 0.8.13 can pay a silent payment code. Paste an `sp1…` address into Send and the wallet derives a fresh on-chain address only the recipient can recognise, pays it, and shows you both on the receipt. What Winnow cannot do is receive at one. The reason is the reason every light wallet that does receive has a company behind it.

## Why your phone can't see a silent payment

A light wallet finds its money with compact filters: one small summary per block, listing every address the block touched. The phone checks the addresses it owns against each summary and downloads only the blocks that match. That works because the phone knows its addresses before anyone pays them.

A silent payment goes to an address that does not exist until the sender makes it, from the sender's own coins and your public code. No list of your addresses could hold it in advance. To find it, your phone needs one small number from every eligible transaction in every block, about 33 bytes each, multiplies each by a key only it holds, and only then has an address to check against the filter.

Those 33 bytes are not in the filters, and cannot be: a filter is a bag of hashes, and you cannot unhash a bag. Someone has to compute and serve them, and today that someone is always a server. Cake Wallet and Nunchuk run one for their users. Sparrow talks to an Electrum server that keeps the data. BlindBit publishes an open one. The server never learns which coins are yours, but it learns your IP and which blocks you care about, and when BlindBit changed its API, every wallet built on the old version stopped working. Winnow ran a server like that once and retired it.

The other honest answer is Electrum's: run your own node, which sees every transaction and can scan for you. If you have a node, that is the right answer. If you have a phone, it is not an answer at all.

## What the backup holds

Here the two promises collide. Even if the data were free, restoring from twelve words would mean asking for those 33 bytes from every block since the wallet was born: 6 GB for a wallet as old as Taproot, by [one careful measurement](https://github.com/bitsagarob/silentpayments-measurements). No phone will do that. Every wallet that offers "restore from your words" and also receives silent payments is quietly relying on a server to do the remembering.

Winnow never made that promise. Its backup is a file, and the file remembers. It holds the height the wallet has scanned to, so a restore picks up where it left off. It holds your coins and your history. It holds the next address to hand out, which no rescan could recover, because an address nobody has paid leaves no mark on the chain. Since 0.8.13 it holds the silent payment code behind each payment you sent, because the address it paid is unique to that transaction and the history could not otherwise say who got it. The iCloud copy adds your address book and labels, sealed on the phone before it leaves, refreshed whenever the wallet changes.

A wallet with a memory can receive silent payments without a server. Add three things to the file, the key that makes each received coin spendable, how far the scan has got, and the labels in use, and the phone never asks anyone for history it already holds. A week offline costs about 24 MB of catch-up. The 6 GB question is not answered. It is declined, and the decline is the design.

## What a peer could serve

That leaves the 33 bytes per transaction, going forward, and they need not come from a company. Bitcoin Core computes them as of this autumn, and already serves per-block summaries to light wallets over the filter protocol Winnow reads today. A second kind of "filter", holding the raw points instead of a bag of hashes, would travel over the same messages, chain its headers the same way, and need no change to consensus. A companion note, "Silent Payments on a Phone: What a Peer Could Serve", says what such a patch would touch and where it would meet resistance.

Core moves slowly, and should. A wallet need not wait. Winnow checks on about 6,900 Bitcoin peers every day and ships the list in every build; today it says which peers serve filters, and it could say which serve tweaks. A wallet that ships every two weeks can follow a protocol that is still settling without stranding anyone.

## What a peer cannot promise

One thing stays open. A peer that serves these points can leave one out and hide one payment, and nothing in the protocol proves it did. Filters have the same weakness today, and light wallets live with it by asking several peers and comparing. Anyone who cannot accept that bargain has the Electrum answer waiting.

The choice is not between privacy and convenience. It is between a wallet that remembers and a wallet that asks someone else to. Winnow chose the memory.
