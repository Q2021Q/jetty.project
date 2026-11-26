package jettypending;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

import org.junit.jupiter.api.extension.BeforeTestExecutionCallback;
import org.junit.jupiter.api.extension.ConditionEvaluationResult;
import org.junit.jupiter.api.extension.ExecutionCondition;
import org.junit.jupiter.api.extension.ExtensionContext;

/** Selects original invocations without changing their bodies or fixtures. */
public final class PendingCases implements ExecutionCondition, BeforeTestExecutionCallback
{
    private static final Map<String, Integer> CASES = loadCases();

    private static Map<String, Integer> loadCases()
    {
        Map<String, Integer> cases = new HashMap<>();
        try (var input = PendingCases.class.getResourceAsStream("/pending-cases.tsv"))
        {
            if (input == null)
                throw new IllegalStateException("Missing pending-cases.tsv");
            try (var reader = new BufferedReader(new InputStreamReader(input, StandardCharsets.UTF_8)))
            {
                for (String line; (line = reader.readLine()) != null;)
                {
                    String[] fields = line.split("\t");
                    cases.put(fields[0], Integer.valueOf(fields[1]));
                }
            }
        }
        catch (Exception failure)
        {
            throw new IllegalStateException("Cannot load pending selection", failure);
        }
        return Map.copyOf(cases);
    }

    @Override
    public ConditionEvaluationResult evaluateExecutionCondition(ExtensionContext context)
    {
        if (context.getTestMethod().isEmpty())
            return ConditionEvaluationResult.enabled("Test container");
        String key = context.getRequiredTestClass().getName() + "#" + context.getRequiredTestMethod().getName();
        Integer index = CASES.get(key);
        if (index == null)
            return ConditionEvaluationResult.disabled("outside-eight-case-selection");
        if (index == 0 || context.getUniqueId().endsWith("[test-template-invocation:#" + index + "]"))
            return ConditionEvaluationResult.enabled("Requested pending case");
        if (!context.getUniqueId().contains("[test-template-invocation:"))
            return ConditionEvaluationResult.enabled("Parameterized test container");
        return ConditionEvaluationResult.disabled("outside-eight-case-selection");
    }

    @Override
    public void beforeTestExecution(ExtensionContext context)
    {
        System.err.println("PENDING_CASE " + context.getUniqueId() + " " + context.getDisplayName());
    }
}
