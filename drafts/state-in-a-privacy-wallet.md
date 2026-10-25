# The State a Wallet Keeps

Draft — Alex Newman · October 25, 2026

*A follow-up to [Bitcoin Beyond Conspiracy Theories](/blog/bitcoin-beyond-conspiracy-theories/): a privacy wallet on a phone has to remember a lot, and phones get restored, replaced and copied. Here's what Winnow remembers, what it refuses to remember, and why the code that handles state is where proofs pay off.*

The curve has one right answer for every input. A wallet's state doesn't. It depends on what happened before: which blocks the phone saw, which addresses it handed out, which spends are still in flight. That's where the bugs I worry about most live, and it's the part of a phone wallet that's hardest to get right.

## What a privacy wallet has to remember

A wallet that asks no server about its addresses has to remember more than one that does. Winnow learns about the chain from compact block filters, from BIP157 and BIP158. It downloads a small filter for each block, checks its own scripts against the filter on the phone, and fetches only the blocks that match. No server learns which addresses are its.

The price is state. The phone has to remember where it stopped scanning, which coins it owns and which spends are in flight. It has to remember which addresses it has handed out, and, for a multisig account, every signer's key.

Some of that is a privacy matter in itself. Hand out an address twice and anyone watching can link the two payments. So the phone keeps counters for its next receive and change addresses. It also scans 20 addresses past each one, so a payment to an address it lost track of still turns up and moves the counter forward.

## Phones forget, and phones get copied

A phone is a bad place to keep state. The app can be killed in the middle of a write. It gets deleted and reinstalled, or restored onto a new phone from a backup that's days old. Two phones can be restored from the same backup. And the chain itself rewrites recent history in a reorg.

Each of those is a way for remembered state to be wrong. The native stack's [security log](https://github.com/winnowwallet/winnow/blob/native-secp256k1-main/docs/security/findings.md) has a run of them in multisig bookkeeping, all found and fixed before release:

- **A zero-value payment** to an account address, which anyone who knows the address can make, stopped the whole wallet's sync, not only the account's. Every later scan failed on the same block. (SEC-030)
- **A losing spend.** When another signer's spend, or a replacement, confirmed instead of mine, my spend's change stayed in the balance for good, and its other inputs stayed reserved, so the account showed less than it held and couldn't spend it. (SEC-031)
- **Too short a lookahead.** The phone watched two addresses past an account's last one, but every signer hands out its own, so a payment further out was never found. (SEC-032)
- **A reorg.** After one, the phone released coins whose spend was still in flight. The reorg had taken the spend's block, but every node had put the spend back in its mempool, so the next spend the phone built would have conflicted with it. (SEC-033)

None of these is a cryptography bug. Each is the phone remembering something that stopped being true.

## What Winnow refuses to remember

The safest state is the state you don't keep. Winnow's signer remembers nothing between signatures. BIP340 makes each nonce from the private key, the message and 32 fresh random bytes, so there's no counter to advance and no session to finish later. Nothing the signer needs is in a file.

That's what makes the iCloud backup safe to restore. Winnow uploads an encrypted backup by default. It holds the recovery phrase, sealed with AES-256-GCM, and the public state of the wallet: its descriptor, coins, history and address counters. On the native stack it carries every multisig account's descriptor too. On the phone, the key lives in the keychain, set to this device only, and the app's own files are excluded from device backups. The copy in iCloud is the sealed phrase, under a wrapping key kept in iCloud Keychain, so the key is backed up automatically without the keychain item itself ever syncing. While a send is pending, the backup waits. Restore an old backup on a new phone and you get the phrase back and a slightly stale view of the coins, which the next scan fixes. You can't get a signer that repeats itself, because there's nothing for it to repeat.

Stateful protocols are different. [MuSig2](https://github.com/bitcoin/bips/blob/master/bip-0327.mediawiki) says it plainly: its signers "are stateful", and the same secret nonce must never sign twice, because two partial signatures made with one nonce give away the key. Picture a MuSig2 signing session that started before a backup. Restore that backup and run the session again, and the restored phone can sign with a nonce it has already used. NBitcoin and btcec ship MuSig2, and noble ships FROST, which keeps the same kind of nonce. Each leaves that bookkeeping to the app.

I built MuSig2 for Winnow and parked it. The multisig that ships is the script-path kind, where each signer makes an ordinary BIP340 signature, so none of this applies to it. The native build goes one step further: it refuses a backup that carries a MuSig2 account, rather than restoring it without that account.

## SHRINCS

[SHRINCS](https://delvingbitcoin.org/t/shrincs-324-byte-stateful-post-quantum-signatures-with-static-backups/2158) is where state stops being optional. It's a post-quantum signature scheme for Bitcoin, built only from hash functions, from Jonas Nick and Mikhail Kudinov at Blockstream Research and now a working group. It's prototype cryptography: the [draft BIP](https://groups.google.com/g/bitcoindev/c/HbVboXIFiG8) says not to use it in production.

Its small signatures come from one-time keys, so the signer keeps a counter of how many it has made. Reuse a count, and anyone who sees both signatures can forge a new one. In the August 2026 draft, the smallest stateful signature is 548 bytes. Every key also has a stateless fallback, and that signature is 5,777 bytes.

Its answer to backups is the part that matters for Winnow. The seed is a static backup. A device restored from it marks its state as lost and signs only on the stateless path from then on, and "if in doubt", any signer can fall back to it.

For Winnow that would mean three things:

- The counter would have to live where the signing key lives, on the phone and nowhere else.
- It could never go in the iCloud backup. Restoring an old copy, or the same copy on two phones, would hand out the same count twice.
- Every phone restored from the backup would sign stateless, about ten times larger and costlier, until its coins move to a fresh key.

Today a wallet can simply choose stateless signing. If Bitcoin moves to something like SHRINCS, that choice goes away, and the backup has to be designed around a counter it can't carry.

## Why this is the code to prove

The curve's arithmetic was the first thing I proved, because it has a tidy specification: one right answer, for every input. State code is messier, and that's the argument for proving it, not against. Its bugs don't show on the happy path. They show after a reorg, a restore or another signer's spend, which tests rarely set up and fuzzers rarely reach. All four bugs above were found by reading and planning, not by a test failing.

The first trial is [draft pull request #248](https://github.com/winnowwallet/winnow/pull/248). It's a Lean specification of spend review, the code that decides what a signer is shown before it signs a multisig spend. That's which outputs are the account's own, what the fee is, and which path can finish it. The specification generated 1,506 test cases that the real code has to match. Of 27 bugs I planted in the Swift, the existing tests caught 8, and the specification caught all 27. It also found a real bug: review crashed on a coin stored at the very top of the block-height range, which a restored backup can carry. That's fixed.

A specification is only as good as my reading of what the code should do. #248 says so itself: if an intended rule is wrong, a model written from the same intent agrees with the bug. That's why its rules are short enough to read against the BIPs. What I'd specify next is the state itself: restoring a backup, old copies and two phones included, and rolling the account back across a reorg. Neither is done.
