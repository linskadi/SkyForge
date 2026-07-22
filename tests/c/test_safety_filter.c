#include <assert.h>
#include "../../templates/c/safety_filter.h"

static void test_init_sets_safe_state(void)
{
    SkyforgeSafetyFilter filter;

    skyforge_safety_filter_init(&filter);

    assert(filter.initialized == true);
    assert(filter.fault_detected == false);
    assert(filter.last_output == 0.0);
}

static void test_nominal_step_stays_in_contract(void)
{
    SkyforgeSafetyFilter filter;
    double output;

    skyforge_safety_filter_init(&filter);
    output = skyforge_safety_filter_step(&filter, 100.0);

    assert(output >= 0.0);
    assert(output <= 20000.0);
    assert(skyforge_safety_filter_faulted(&filter) == false);
}

static void test_out_of_range_input_sets_fault(void)
{
    SkyforgeSafetyFilter filter;
    double output;

    skyforge_safety_filter_init(&filter);
    output = skyforge_safety_filter_step(&filter, 25000.0);

    assert(output == 0.0);
    assert(skyforge_safety_filter_faulted(&filter) == true);
}

int main(void)
{
    test_init_sets_safe_state();
    test_nominal_step_stays_in_contract();
    test_out_of_range_input_sets_fault();
    return 0;
}
