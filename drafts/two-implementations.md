# Two Implementations Are Better Than One

Draft — Alex Newman · October 20, 2026

*Part 2 of the series that starts with [Bitcoin Beyond Conspiracy Theories](/blog/bitcoin-beyond-conspiracy-theories/): why a second implementation is worth having, when it is dangerous, and why AI suddenly makes it affordable.*

Winnow's single-key build replaced libsecp256k1 with its own Swift secp256k1. That gave the wallet a second implementation of the same mathematics, written separately, in a different language. This part is about what a second implementation is good for, where Bitcoin learned to be careful about them, and why writing one is no longer a multi-year project.

## When one implementation is the rules

Bitcoin's history has two famous examples of what happens when an implementation detail quietly becomes a rule.

In March 2013 a large block split the chain. [BIP50](https://github.com/bitcoin/bips/blob/master/bip-0050.mediawiki) tells it: versions before 0.8 used Berkeley DB and configured too few database locks to process that block, while 0.8 used LevelDB and processed it without trouble. A lock limit that nobody had written down was, in effect, a consensus rule. The split ended when large pools downgraded so the older rules won.

Two years later [BIP66](https://github.com/bitcoin/bips/blob/master/bip-0066.mediawiki) made strict DER signatures a consensus rule, and its motivation is blunt. Bitcoin's reference implementation relied on OpenSSL to validate signatures, so OpenSSL's parser defined which blocks were valid. OpenSSL "is not designed for consensus-critical behaviour" and did not promise to stay bug-for-bug compatible, and when OpenSSL 1.0.0p and 1.0.1k changed how they read non-DER encodings, some nodes rejected the chain.

Both lessons point the same way for consensus code: everyone must agree exactly, so a second implementation is a liability unless it reproduces every quirk of the first. That is why the specification of Bitcoin's rules is, in practice, Bitcoin Core.

A wallet's signing code is not consensus code. A wallet does not decide which blocks are valid; it produces signatures that the network's validators either accept or reject. For that job, a second implementation is not a fork risk. It is an oracle.

## What two implementations bought here

The Swift module was checked against libsecp256k1 the whole way, and the comparison earned its keep.

- **Byte-for-byte signatures.** BIP340 signing is deterministic given the auxiliary input, so two correct implementations must produce identical bytes. A signature that verifies but differs by one bit is a failure. That is a much sharper test than "it verifies", and it is only available when there is another implementation to compare with.
- **A surprise in the oracle's own wrapper.** The Swift wrapper around libsecp256k1 that Winnow used passed a tweak of any length straight to C functions that read exactly 32 bytes. A longer tweak was silently cut short, and a shorter one sent the C code reading past the end of the array. The C function cannot check a length it is never given; the wrapper did not check either. The native module refuses any tweak that is not 32 bytes, so those cases could not be compared at all and became native-only refusal tests. Nobody was looking for that. Putting two implementations side by side found it.
- **Two oracles that must agree.** When the live comparison was replaced by recorded answers, each answer was computed twice, by BIP340's Python reference and by a small C program over libsecp256k1, and written down only where the two agreed. Neither is the code under test.
- **Interop on a real network.** On a separate [branch](https://github.com/winnowwallet/winnow/commit/dae4b74576d0c5aa179c90c9c71a677c95b06bde), MuSig2 is back as a raw two-signer account. The phone's Swift implementation of BIP327 and Bitcoin Core's own, built on libsecp256k1, take turns adding nonces and partial signatures to the same transaction, and Core must accept, mine and find the result. Two implementations of a protocol that neither side can fake.

This is the idea behind [Project Wycheproof](https://github.com/C2SP/wycheproof), the shared test vectors for "known attacks, specification inconsistencies, and other various implementation bugs" across cryptography libraries. Bugs hide in the places one implementation's authors never thought to test. Another implementation's authors thought of different places.

## Why this used to be rare, and is not now

A second implementation of serious cryptography used to cost years of an expert's time. Most projects reasonably decided not to pay it and used the established library, which is how one library comes to define correctness for everyone who calls it.

That cost has collapsed. Winnow's module, its tests, the recorded fixtures and their generators, the removal of shared accounts and a TestFlight release took about two days, with Claude writing most of the code while I reviewed, directed and tested it on a phone. The [introduction](/blog/bitcoin-beyond-conspiracy-theories/) opens with another example of the same shift: Claude reconstructing how the NIST curve seeds were generated in under half an hour, a question that had sat open for decades.

The most interesting example goes further than a second implementation. [Verified Garbage](https://github.com/pyca/verified-garbage/tree/2fa57c651a97a18e3e1c03503b583f62db9d9e2a) is an experimental cryptography library under the pyca organization, implemented by language models. Each primitive is assembly, written against a Lean model of the processor and proved in Lean to be correct against a specification, memory safe, and constant time. Its P-256 ECDSA verification [on x86-64](https://github.com/pyca/verified-garbage/pull/721) and [on AArch64](https://github.com/pyca/verified-garbage/pull/797) was merged on 3 and 4 October from commits authored by Claude. The point addition there is a complete formula, so there are no exceptional cases to branch on. The library has since added [secp256k1 on AArch64](https://github.com/pyca/verified-garbage/pull/1342) too: keys, ECDH and ECDSA, but not BIP340, BIP32 or Taproot tweaks. Its proofs rest on stated assumptions. On AArch64 the constant-time guarantee holds only if the caller has set DIT, and the Rust around the verified functions is tested, not proved. Even so, it is a different class of evidence from mine. My tests show agreement on the inputs I chose. A machine-checked proof covers every input, within the model it trusts.

## Where AI makes this worse

Cheap implementations are only valuable if they are independent, and AI threatens exactly that. A model that has read libsecp256k1 can reproduce its structure, and with it any mistake the two share. A test written by the same model that wrote the code can encode the same misunderstanding twice, and pass.

So the rules matter more, not less:

- **The expected answer never comes from the code under test.** Not from the Swift module, and not from a test the same session generated by running it.
- **Oracles come from somewhere else.** A specification's reference implementation, an established library in another language, published test vectors, and ideally two of them that must agree.
- **The network is the last word.** A signature Bitcoin Core accepts and miners include is checked by code nobody in this project wrote.
- **Proofs beat agreement.** When proofs are available, as in Verified Garbage, they cover what no finite set of tests can.

Two implementations, one of them written in two days with an AI, is not a reason to trust either one more. It is a way to find out where they disagree, and every disagreement is a question somebody would otherwise have had to think to ask. Part 3 puts both implementations to work on a protocol with two signers: MuSig2.
