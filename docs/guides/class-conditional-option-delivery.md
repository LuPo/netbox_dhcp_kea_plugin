---
title: Class-conditional option delivery
description: Modelling DHCP options that should only reach specific device classes — and that may vary per subnet or per class within a subnet.
---

# Class-conditional option delivery

Many DHCP options are only meaningful to one kind of device — wireless access points fetching a controller FQDN, IP phones fetching a SIP server, PXE clients fetching a boot file, thin clients fetching a connection broker. The pattern in all these cases is the same:

1. Identify the device by **vendor-class-identifier** (DHCP option 60) or another classifier.
2. Deliver a **specific option** only to the matched clients.
3. Sometimes the *value* of that option depends on **where** the client lands — controller-per-site, TFTP-server-per-floor, broker-per-region.

This page describes the three patterns the plugin supports for this, when to use each, and the legacy ISC `dhcpd` idiom that should **not** be carried over verbatim.

!!! info "Terminology used in this guide"

    - **Vendor matcher class** — a `ClientClass` whose `test_expression` matches a specific vendor-class-identifier string (e.g. `option[60].text == 'Access Point ModelA'`). Carries no option data.
    - **Delivery class** — a `ClientClass` whose only job is to associate option data with a `member()`-test gate. Typically `only_in_additional_list=True` so it's not auto-evaluated for every packet.
    - **Umbrella class** — a `ClientClass` whose `test_expression` is a chain of `member()` calls over several vendor matcher classes. Useful for explicit gating via `Subnet.evaluate_additional_classes`.

!!! important "Subnet *selection* vs. class *evaluation* — two different things"

    Two `Subnet` fields look similar but do very different things:

    - **`Subnet.client_class`** (single FK) → Kea's `client-class` on subnet. **Restricts subnet selection** — clients outside this class cannot get a lease from this subnet at all.
    - **`Subnet.evaluate_additional_classes`** (M2M) → Kea's `evaluate-additional-classes` on subnet. **Triggers class evaluation** for clients already being served by this subnet. The classes listed here are evaluated; their `option_data` is delivered only if their tests pass. It does **not** restrict who can get a lease.

    All option-gating in this guide uses `evaluate_additional_classes` (delivery gating). Use `client_class` only when you actually want to refuse leases to non-matching clients — e.g. a VLAN dedicated to wireless APs.

---

## When to use which pattern

| Question 1 | Question 2 | Pattern |
|---|---|---|
| Does the option value vary across subnets? | — | **No → [Pattern A](#pattern-a-uniform-value-attach-to-the-class)** |
| ↓ Yes | Within a single subnet, do all matched device classes share the same value? | **Yes → [Pattern B](#pattern-b-per-subnet-value-attach-to-the-subnet)** |
| ↓ Yes | ↓ No | **Pattern C — [delivery classes](#pattern-c-per-subnet-and-per-class-delivery-classes)** |

---

## Pattern A — Uniform value: attach to the class

Use when the option's value is the same wherever the matching client class lands. Example: a fleet of thin clients that always fetch their broker from `https://broker.example.com/v1`, regardless of subnet.

### Model objects

- **1 `OptionDefinition`** for the option (`name`, `code`, `option_type`, `option_space`).
- **1 `ClientClass`** with the vendor-class-identifier test expression *and* the `OptionData` attached via the `option_data` M2M.

### Rendered Kea (illustrative)

```json
{
  "client-classes": [
    {
      "name": "ThinClient-VendorA",
      "test": "option[60].text == 'ThinClient-VendorA'",
      "option-data": [
        { "name": "broker-url", "data": "https://broker.example.com/v1" }
      ]
    }
  ]
}
```

!!! tip "Why this is the simplest pattern"
    The option-data lives on a single row and travels with the class. No per-subnet wiring, no gating logic, no `evaluate-additional-classes` plumbing. Reach for this first.

---

## Pattern B — Per-subnet value: attach to the subnet

Use when every matched device gets the same value *within* a subnet, but different subnets carry different values. Example: a wireless access-point fleet where each building's APs register to that building's controller FQDN.

### Model objects

- **1 `OptionDefinition`** for the option.
- **N `ClientClass` rows** for the individual vendor matchers (one per model / vendor string). No option data attached.
- **M `OptionData` rows**, one per distinct *value* across the estate (e.g. 6 unique controller FQDNs covering 100 subnets).
- For each subnet: attach the appropriate `OptionData` via the subnet's `option_data` M2M.

### Rendered Kea (illustrative)

```json
{
  "subnet4": [
    {
      "subnet": "10.0.71.0/25",
      "option-data": [
        { "name": "controller-host", "data": "controller-a.example.com" }
      ]
    },
    {
      "subnet": "10.0.72.0/25",
      "option-data": [
        { "name": "controller-host", "data": "controller-b.example.com" }
      ]
    }
  ]
}
```

### What about gating to AP-only clients?

The option is now on the subnet, so technically it's offered to every client in the subnet — but Kea only puts an option on the wire if the client requested it in the parameter-request-list (PRL) **or** the option-data carries `always-send=true`.

For typical class-specific options (option 43, option 66/67 for PXE, option 150 for VoIP TFTP servers), the targeted devices request the option and other devices do not. PRL filtering achieves the gating without further configuration.

!!! warning "When PRL filtering is not enough"

    If your option might be requested by clients that *shouldn't* receive it (a misbehaving phone asking for option 43, a sloppy PXE stack…), you can gate **option delivery** without restricting subnet access:

    1. Create an **umbrella class** with `only_in_additional_list=True` and a test chaining `member('VendorA') or member('VendorB') or …`.
    2. Move the `OptionData` from the subnet onto that umbrella class (`ClientClass.option_data` M2M).
    3. List the umbrella class in the subnet's `evaluate_additional_classes`.

    Now every client in the subnet still gets a lease normally, but Kea evaluates the umbrella class for each lease and only emits the option-data when the `member()` test passes.

    This is **purely an option-delivery gate**, not a subnet-membership gate. The subnet's `client_class` FK is what restricts which clients can lease from the subnet at all — don't confuse the two.

    For per-class value variation, skip the umbrella entirely and use [Pattern C](#pattern-c-per-subnet-and-per-class-delivery-classes).

---

## Pattern C — Per-subnet *and* per-class: delivery classes

Use when clients in the same subnet need *different* values for the same option depending on which class matched. Example: a mixed-vendor wireless deployment where Vendor A APs register to one controller and Vendor B APs register to another, but both share the building's subnet.

### Why the simpler patterns don't fit

- Pattern A puts the value on the class globally — can't differ per subnet.
- Pattern B puts one value on the subnet — can't differ per class within the same subnet.
- Kea pools cannot overlap address ranges, so creating two pools just to attach different option-data to the same address space doesn't work.

The Kea-native answer is per-entry **`client-classes` qualifier** inside the subnet's `option-data` array. Today's plugin doesn't carry that qualifier on the `Subnet.option_data` M2M, so we express the same semantics via *delivery classes*.

### Model objects

- **1 `OptionDefinition`** for the option.
- **N vendor matcher `ClientClass` rows** (test expression only, no option data).
- **K `OptionData` rows**, one per distinct value.
- For each unique `(subnet, value)` pair that needs gating, **one delivery class**:
    - `test`: `member('VendorClassA') or member('VendorClassB') or …` — list the vendor matchers that should receive this value in this subnet
    - `option_data` M2M: the `OptionData` for that value
    - `only_in_additional_list = True`
- For each subnet: list the relevant delivery classes in `evaluate_additional_classes`.

### Example

Subnet `10.0.71.0/25` houses APs from two vendors. Vendor A devices should get `controller-x.example.com`; Vendor B devices should get `controller-y.example.com`.

| Object | Test | Attached `OptionData` |
|---|---|---|
| `VendorA-AP` (matcher) | `option[60].text == 'Access Point ModelA'` | — |
| `VendorB-AP` (matcher) | `option[60].text == 'Access Point ModelB'` | — |
| `delivery-subnet71-cx` (delivery, `only_in_additional_list=True`) | `member('VendorA-AP')` | `controller-host = controller-x.example.com` |
| `delivery-subnet71-cy` (delivery, `only_in_additional_list=True`) | `member('VendorB-AP')` | `controller-host = controller-y.example.com` |

Subnet `10.0.71.0/25`'s `evaluate_additional_classes` lists both `delivery-subnet71-cx` and `delivery-subnet71-cy`.

### Evaluation flow

1. Client lands in the subnet.
2. The matching vendor class fires automatically (e.g. `VendorA-AP`).
3. Subnet-level `evaluate_additional_classes` triggers evaluation of `delivery-subnet71-cx` and `delivery-subnet71-cy`.
4. The `member()` test in each delivery class checks against the vendor classes the client already belongs to. Only the relevant one fires.
5. That delivery class's `option_data` is included in the response.

### Rendered Kea (illustrative)

```json
{
  "client-classes": [
    { "name": "VendorA-AP", "test": "option[60].text == 'Access Point ModelA'" },
    { "name": "VendorB-AP", "test": "option[60].text == 'Access Point ModelB'" },
    {
      "name": "delivery-subnet71-cx",
      "test": "member('VendorA-AP')",
      "only-if-required": true,
      "option-data": [{ "name": "controller-host", "data": "controller-x.example.com" }]
    },
    {
      "name": "delivery-subnet71-cy",
      "test": "member('VendorB-AP')",
      "only-if-required": true,
      "option-data": [{ "name": "controller-host", "data": "controller-y.example.com" }]
    }
  ],
  "subnet4": [
    {
      "subnet": "10.0.71.0/25",
      "evaluate-additional-classes": ["delivery-subnet71-cx", "delivery-subnet71-cy"],
      "pools": [{ "pool": "10.0.71.3 - 10.0.71.118" }]
    }
  ]
}
```

!!! note "Collapsing same-value lines within a subnet"

    If several vendor classes share the *same* value in the same subnet, OR-chain their `member()` calls into a single delivery class rather than creating one per vendor. For example, if Vendor A, Vendor C and Vendor D APs all use controller X in subnet 71, a single delivery class with test `member('VendorA-AP') or member('VendorC-AP') or member('VendorD-AP')` suffices.

---

## Anti-pattern: replicating the ISC `dhcpd` option-space-per-vendor idiom

If you're migrating from ISC `dhcpd`, you'll commonly see this shape:

```text
option space VendorA;
option VendorA.foo code 43 = string;

option space VendorB;
option VendorB.foo code 43 = string;

class "VendorA-Device" {
    match if option vendor-class-identifier = "VendorA";
    vendor-option-space VendorA;
}
class "VendorB-Device" {
    match if option vendor-class-identifier = "VendorB";
    vendor-option-space VendorB;
}

subnet 10.0.71.0/25 {
    option VendorA.foo "value-X";
    option VendorB.foo "value-Y";
    ...
}
```

In `dhcpd`, the *only* way to give option 43 a friendly per-vendor label (`VendorA.foo`, `VendorB.foo`, …) was to declare a separate option space for each vendor and put an identically-typed suboption inside it. That declaration block is a **labeling workaround** for `dhcpd`'s option-space resolution rules, not a wire-level requirement: every `option <Vendor>.foo "value"` assignment produces the same bytes on the wire — option code 43, length N, payload = the string. The vendor name in the option-space label never leaves the server.

In Kea (and therefore in this plugin), you do not need:

- A separate `VendorOptionSpace` row per vendor.
- A separate `OptionDefinition` row per vendor.
- Repeated assignments of the same logical value under different "space" labels.

A single `OptionDefinition` with the option code, type and `option_space='dhcp4'` covers all vendors. The class matching happens via `ClientClass.test_expression`; the value gating happens via attachment (Patterns A/B) or delivery classes (Pattern C).

!!! danger "When `VendorOptionSpace` *is* appropriate"

    `VendorOptionSpace` in this plugin is for **true vendor-encapsulated suboption stacks** — typically option 125 (Vendor-Identifying Vendor-Specific Option, VIVSO) with an IANA enterprise number, or option 43 sub-options that nest multiple typed values inside a single vendor space. If you have one logical option carrying one logical value, you don't need it.

---

## Decision matrix (quick reference)

```text
                  ┌─────────────────────────────────────────────┐
                  │ Does the option value vary across subnets?  │
                  └────────────────────┬────────────────────────┘
                                       │
                ┌──────────────────────┴───────────────────────┐
                │ no                                           │ yes
                ▼                                              ▼
   ╔══════════════════════════╗     ┌──────────────────────────────────────────┐
   ║ Pattern A                ║     │ Within a subnet, do all matched classes  │
   ║ Attach OptionData to     ║     │ share the same value?                    │
   ║ the ClientClass.         ║     └────────────────┬─────────────────────────┘
   ╚══════════════════════════╝                      │
                                  ┌──────────────────┴──────────────────┐
                                  │ yes                                 │ no
                                  ▼                                     ▼
                  ╔══════════════════════════╗     ╔══════════════════════════╗
                  ║ Pattern B                ║     ║ Pattern C                ║
                  ║ Attach OptionData to     ║     ║ Use delivery classes     ║
                  ║ the Subnet. PRL          ║     ║ (one per (subnet, value) ║
                  ║ filtering or umbrella    ║     ║ pair). Reference from    ║
                  ║ class for gating.        ║     ║ evaluate_additional_-    ║
                  ║                          ║     ║ classes on the subnet.   ║
                  ╚══════════════════════════╝     ╚══════════════════════════╝
```

---

## Future direction

The Pattern C "delivery classes" exist only because the current data model can't carry a *per-attachment* class qualifier on the `Subnet.option_data` (or `ClientClass.option_data`) M2M.

A future enhancement under consideration is a through-model:

```python
class SubnetOptionData(NetBoxModel):
    subnet         = ForeignKey(Subnet, on_delete=CASCADE)
    option_data    = ForeignKey(OptionData, on_delete=PROTECT)
    only_for_class = ForeignKey(ClientClass, null=True, blank=True)
```

At render time, `only_for_class` would translate directly into a `client-classes` qualifier on the corresponding option-data entry in the subnet's `option-data` array — the Kea-native expression of Pattern C. The bookkeeping delivery classes would disappear; the data model would carry the gating semantics directly.

Until then, Pattern C is the recommended approach. There is a trade-off worth flagging both ways:

- **Pattern C as it stands** keeps the data model lean: only the existing `ClientClass`, `OptionData`, and `Subnet` tables are involved. No new table to maintain, no migration to land, no extra serializer / form / view scaffolding to keep in sync. The cost is paid in *content* — some extra `ClientClass` rows whose only purpose is to carry a `(member()-test, option-data)` pair.
- **The `SubnetOptionData` through-model** would push the cost the other way: cleaner content (no bookkeeping classes, the gating qualifier lives on the M2M edge), but a new persistent table to model, migrate, version, and expose through forms / serializers / filters. That overhead is worth it once class-scoped option attachment becomes a routine pattern across many domains; it is hard to justify for a single niche use case.

In short, Pattern C avoids a schema change by accepting a bit of content noise — the right trade-off while class-scoped option attachment is rare. The output is functionally identical to what the through-model would emit, so a future migration that introduces `SubnetOptionData` can rewrite the existing delivery-class rows into through-model edges without affecting the rendered Kea config.
