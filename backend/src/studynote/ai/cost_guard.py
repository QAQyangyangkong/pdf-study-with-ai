"""Conservative token estimates; ledger reservations live in the database."""


def estimate_tokens(messages):
    return sum(len(message["content"].encode("utf-8")) for message in messages) + 256


def estimate_cost(config, input_tokens, output_tokens):
    return (input_tokens * config.input_price + output_tokens * config.output_price) / 1_000_000
