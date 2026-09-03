def compute_cost_micros(
    prompt_tokens: int,
    completion_tokens: int,
    input_cost_per_mtok: int,
    output_cost_per_mtok: int,
) -> int:
    return (
        prompt_tokens * input_cost_per_mtok + completion_tokens * output_cost_per_mtok
    ) // 1_000_000