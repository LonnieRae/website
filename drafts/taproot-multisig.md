# Hardware Wallets, Two of Three

Draft — Alex Newman · October 23, 2026

*A follow-up to [Bitcoin Beyond Conspiracy Theories](/blog/bitcoin-beyond-conspiracy-theories/): one hardware wallet is one thing to lose. Two that must both sign are safer, and twice as easy to get locked out of. Add a phone whose key iCloud can restore, ask for any two of the three, and you keep the safety without the lockout. Here's the argument, how Winnow builds it, and what isn't tested yet.*

**Shelved 23 October 2026.** This replaces the MuSig2 draft. Keep it shelved until a physical Ledger has signed.

Hardware wallets are good at one thing: they keep the key off your computer and show you the payment on their own screen before they sign. Most setups then waste that by depending on a single device. This is the case for a better arrangement, and for using iCloud in it.

## One device is one thing to lose

With one hardware wallet, the device is the key. Lose it, break it or have it stolen, and your fallback is its seed words on paper, which you have to keep as safely as the device itself. One device, one failure, and the paper is the plan.

## Two that agree

Put two hardware wallets in a 2-of-2, and nothing moves unless both sign, each after showing the payment on its own screen. A thief needs both devices. A bug in one device's firmware, or a screen that lies, isn't enough on its own, because the other device has to show and approve the same payment. Two devices from different makers, running different code, have to agree before a coin moves. That's the argument for two implementations of the curve, applied to signing.

The problem is availability. Lose either device and the coins can't move until you go back to its seed words. A 2-of-2 doubles what you have to keep safe and halves what you can afford to lose.

## A phone as the third key

So add a third key and ask for any two. In Winnow, the third key is the phone's.

Day to day, the phone and one hardware wallet sign, or both hardware wallets do. If a hardware wallet breaks, the phone and the other one sign. If the phone is lost, the two hardware wallets sign, and a new phone can rejoin.

That new phone gets its key back from iCloud. Winnow's backup holds the phone's recovery phrase, sealed with AES-256-GCM under a key kept in iCloud Keychain, and the account's descriptor. The descriptor matters as much as the key: it's the list of every signer's public key, and without it even all three keys can't find the coins. So whoever controls your Apple account could, in principle, recover that one key.

In a single-key wallet that would be a bad trade. As one key of three, it's the right one. The phone's key can't spend alone. Taking your coins would need your Apple account and one of your hardware wallets. In return, losing the phone costs nothing, losing a hardware wallet costs nothing, and nobody has to find a sheet of paper. iCloud gives up some of the secrecy of one key and buys availability for all three.

## What "better" has to mean

That's the claim: hardware wallets, but arranged so that losing any one thing doesn't lose the coins, and every signer checks the payment for itself. It only holds if each part does its job.

- **Each signer checks.** The hardware wallet shows the payment on its screen. The phone runs its own review of the spend before it signs, and that review is held to a Lean specification in [draft pull request #248](https://github.com/winnowwallet/winnow/pull/248).
- **The account matches Bitcoin Core.** A differential test builds 60 accounts on each of two seeds and has Core check the descriptors, addresses, signatures and every spend. More on that below.
- **There's a way back.** An optional recovery path lets fewer signers move a coin that has sat still long enough.
- **It's honest about what's untested.** No physical Ledger has signed yet.

## One output, one script

An account is a single Taproot output: `tr(NUMS, sortedmulti_a(2, key1, key2, key3))`. The internal key is one nobody can sign for, so the only way to spend is the script. It asks for two of the three signatures.

Each signer makes an ordinary BIP340 signature over the BIP342 script-path message. Nobody has to wait on anybody. Each signature is made alone, in any order, and the spend reveals the script and every signature on-chain. It costs about 42 extra vbytes per input for a 2-of-2, and anyone can see it's multisig.

## Why the curve code didn't grow

I started with MuSig2, which merges several keys and signatures into one, so a spend looks like any single-key payment. That needs key aggregation, nonces that must never repeat, and two rounds of messages. I built it, shipped it as 0.8.8, and parked it.

Script-path needed none of that. Between `3794057` and `7b7ff30`, the curve module's Swift files didn't change. The 781 lines that were there for a single key were enough.

## A Ledger as one of the signers

I wanted hardware people already own. SeedSigner can't do this. Version 0.8.7 refuses any key inside a Taproot script tree, and it trims script-path signatures away on the way back to the phone. The Satochip fork that drives a card signs ECDSA only.

Ledger's Bitcoin app signs these leaves, and Winnow talks to it without linking any Ledger code. The client is written from the app's protocol: the Bluetooth framing, Merkle proofs and BIP388 wallet policies, in a folder of its own. The phone pairs with the Ledger and registers the account on it, and the Ledger shows the policy for approval. "Pair a Ledger" builds a 2-of-2 between you and the device. For anything bigger, "New multisig account" has an "Include a Ledger" switch, with or without a recovery path. "Verify on Ledger" shows a receive address on the device's screen. When you spend, the Ledger shows the payment before it signs, and the phone adds the signature only after it verifies on the leaf the Ledger says it signed, against the sighash the phone computed. It's all in Advanced mode, and Simple mode refuses it.

Two version numbers matter here. Version 2.1.2 signs `multi_a` leaves. A recovery leaf needs 2.2.0, because it's miniscript. And if the recovery leaf reuses a signer on `/<2;3>/*`, you need 2.2.1, because earlier versions return the wrong leaf hashes for keys on that path.

The internal key has to be an xpub, because BIP388 wallet policies accept only extended keys. I build it the way Liana does: BIP341's NUMS point, with the SHA-256 of the signers' keys as the chain code. Every child of that point is still unspendable.

## A trustee instead of a second device

A 2-of-3 needs three keys, and they don't all have to be yours. One of them can sit on someone else's phone. It can belong to a trustee, someone you trust to help and not to spend: a relative, a friend, a lawyer.

Then you sign with your phone and your Ledger, and the trustee's phone sits idle. If you lose the Ledger, your phone and the trustee's sign together. If you lose your phone, the Ledger and the trustee sign. The trustee alone can't spend, and neither can a thief with one device. The trustee joins the way the second phone does in the test notes: their phone shows its key, you build the account with it, and the descriptor goes back to them.

The recovery path in the next section can change that. If it lets any one of the same three signers spend alone after the delay, the trustee can spend alone after the delay too. That's a choice to make on purpose. The other mode, a separate recovery key that you keep somewhere else, gives the trustee nothing extra.

## A way back for coins that sit still

Version 0.8.10 adds a second leaf. It's either `and_v(v:pk(K),older(N))` or `and_v(v:multi_a(m,…),older(N))`, with N from 1 to 65,535 blocks.

Once a coin has sat still for N blocks, fewer of the same signers can move it, or a separate recovery key can. A reused signer signs that leaf from its own `/<2;3>/*` branch, because BIP388 doesn't let one derived key appear in two leaves. The input's sequence number picks the path. A recovery spend only selects coins that are at least N blocks deep.

Testing against Bitcoin Core turned up one disagreement. Core writes a two-leaf tree into the PSBT in reverse order. Both orders are valid, but Winnow's combiner refused the two values. Winnow now writes Core's order, and the combiner stays strict.

## A recovery wallet

[Winnow Rescue](https://github.com/winnowwallet/winnowrescue) is a separate project, and the other half of this story. It's a rescue-only tool that gets coins out of any old wallet, from recovery words, a single key or another wallet's export, and sweeps them into a taproot account you already own. That account can be one of these. Its core is a Rust library that wallets are meant to embed, and the standalone tool is a command line and a desktop window. It's open source under the MIT license.

It's early. Only the core exists, about 11,800 lines that read words and keys, plan which derivation paths to check, verify header chains and coin proofs, and work through discovery in tiers. The command line, the window and the Electrum client are stubs, and signing and sweeping come in a later milestone. It can't move a coin yet.

Its [plan](https://github.com/winnowwallet/winnowrescue/blob/2ee03b5/docs/plan.md) has a later step that matters here: descriptors and wallets made elsewhere. It would discover the coins, sign where it holds a key, and otherwise build a PSBT for the device that can. For a multisig account that's the lost-phone story. Your Ledger and the trustee sign a PSBT that the recovery tool built, and the coins move to a new account. None of that is built.

Rescue takes its curve from libsecp256k1, and that's on purpose. If the Swift curve in Winnow ever has a bug nobody's found, the tool that rescues coins shouldn't share it. [Two Implementations, Then a Proof](/blog/two-implementations/) is about why.

## An exchange as a signer

Picture the third key sitting with an exchange instead of with a person. You sign with your phone and your Ledger. If you lose one, the exchange co-signs, after it checks that it's you. And if the exchange embeds Rescue's core, it could also take in coins from a customer's old wallets and sweep them straight into that account.

Nothing like this exists, in Winnow or in Rescue, and I haven't discussed it with an exchange. The pieces it would need are small. The exchange makes an ordinary BIP340 signature over a spend it can read, and it has to show the payment to a person or a rule, the way a Ledger shows it on a screen. A button that signs whatever it's given isn't enough.

The harder parts are about trust. Rescue's [own design](https://github.com/winnowwallet/winnowrescue/blob/2ee03b5/docs/design.md) leaves service-cosigned wallets out, and two-factor seeds too, since a service holds a key. Its exchange check only asks whether an address is in your deposit list, refuses a login that can trade or withdraw, and never supplies a deposit address. An exchange that signs is a different relationship. In a 2-of-3 it can't spend alone, but anyone who can talk it into signing becomes the second factor, so the exchange's own login becomes part of the wallet's security. That's the design question, more than the code.

## What's tested, and what isn't

Bitcoin Core 31.1 produced the checksums and addresses for four timelocked descriptors, and the tests compare against those. In the signet journey in the 0.8.10 release run, Core cosigns a 2-of-2 spend. After a three-block delay, it accepts and mines a spend that the phone signs alone through the recovery leaf.

A differential test now holds the accounts to Bitcoin Core on a throwaway regtest node ([#250](https://github.com/winnowwallet/winnow/pull/250)). For accounts of two to five signers, Core checks the descriptor checksum, the first addresses and which signatures a spend carries. Every exact set of k signers has to finish a spend that Core accepts and mines, k − 1 must not, and the recovery lock has to open in exactly the right block. Sixty accounts on each of two seeds ran 2,198 and 2,298 checks with no disagreement. It found one bug first: the same signers listed in a different order built a different account. The builder now writes keys in one order. The test needs `bitcoind`, so it runs by hand, not in CI.

Nothing has been signed on a physical Ledger yet. The Ledger tests use Ledger's own policy and address vectors and a software Ledger I wrote from the same documentation, and a fuzz target feeds the client hostile frames, commands and signatures. Agreeing with the simulator proves little: it shows the phone's client is consistent, not that the device agrees. The next test is a Nano X on signet, by hand.

## Where it stands

Two draft pull requests carry this. [#246](https://github.com/winnowwallet/winnow/pull/246) is the native curve, the multisig accounts, the recovery leaf, a fuzz oracle and the Core differential, proposed to Winnow's main branch. Merging it would make this the App Store build, and it would take MuSig2 savings, vaults and cosigner cards out of the shipping app, so that trade has to be decided first. [#247](https://github.com/winnowwallet/winnow/pull/247) is the Ledger signer alone, one commit on top of #246 and split out so #246 can be reviewed and landed without it. Merge #246 first. #247 waits for a Nano X to sign.
