#include "safety_filter.h"

/* [REQ-C-001] [CON-C-001] Contract bounds for DAL demonstration evidence. */
#define SKYFORGE_INPUT_MIN   (0.0)
#define SKYFORGE_INPUT_MAX   (20000.0)
#define SKYFORGE_OUTPUT_MIN  (0.0)
#define SKYFORGE_OUTPUT_MAX  (20000.0)
#define SKYFORGE_ALPHA       (0.385870)

static double skyforge_contract_guard_safety_filter(const double raw_input,
                                                    const double filtered_output,
                                                    bool * const fault_detected)
{
    double safe_output = filtered_output;

    if (fault_detected == ((void *)0))
    {
        safe_output = 0.0;
    }
    else
    {
        *fault_detected = false;

        if ((raw_input < SKYFORGE_INPUT_MIN) || (raw_input > SKYFORGE_INPUT_MAX))
        {
            *fault_detected = true;
            safe_output = 0.0;
        }
        else
        {
            if ((safe_output < SKYFORGE_OUTPUT_MIN) || (safe_output > SKYFORGE_OUTPUT_MAX))
            {
                *fault_detected = true;
                safe_output = 0.0;
            }
            else
            {
                safe_output = filtered_output;
            }
        }
    }

    return safe_output;
}

void skyforge_safety_filter_init(SkyforgeSafetyFilter * const filter)
{
    if (filter != ((void *)0))
    {
        filter->last_output = 0.0;
        filter->initialized = true;
        filter->fault_detected = false;
    }
    else
    {
        /* [REQ-C-001] Null filter cannot be initialized. */
    }
}

double skyforge_safety_filter_step(SkyforgeSafetyFilter * const filter,
                                   const double raw_input)
{
    double filtered_output = 0.0;

    if (filter == ((void *)0))
    {
        filtered_output = 0.0;
    }
    else
    {
        if (filter->initialized == false)
        {
            skyforge_safety_filter_init(filter);
        }
        else
        {
            /* [REQ-C-001] State is already initialized. */
        }

        filtered_output = (SKYFORGE_ALPHA * raw_input)
            + ((1.0 - SKYFORGE_ALPHA) * filter->last_output);
        filtered_output = skyforge_contract_guard_safety_filter(
            raw_input,
            filtered_output,
            &filter->fault_detected);
        filter->last_output = filtered_output;
    }

    return filtered_output;
}

bool skyforge_safety_filter_faulted(const SkyforgeSafetyFilter * const filter)
{
    bool faulted = true;

    if (filter != ((void *)0))
    {
        faulted = filter->fault_detected;
    }
    else
    {
        faulted = true;
    }

    return faulted;
}
