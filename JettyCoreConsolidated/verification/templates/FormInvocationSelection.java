package verification;

import org.junit.jupiter.api.extension.ConditionEvaluationResult;
import org.junit.jupiter.api.extension.ExecutionCondition;
import org.junit.jupiter.api.extension.ExtensionContext;

public final class FormInvocationSelection implements ExecutionCondition
{
    @Override
    public ConditionEvaluationResult evaluateExecutionCondition(ExtensionContext context)
    {
        if (context.getTestMethod().filter(method -> method.getName().equals("testMaxFormContentSizeExceeded") &&
            method.getDeclaringClass().getName().equals("org.eclipse.jetty.test.client.transport.FormTest")).isEmpty())
            return ConditionEvaluationResult.enabled("outside the FormTest comparison");

        String id = context.getUniqueId();
        if (id.endsWith("[test-template-invocation:#8]") || !id.contains("[test-template-invocation:"))
            return ConditionEvaluationResult.enabled("original FormTest invocation 8");

        return ConditionEvaluationResult.disabled("outside the FormTest comparison");
    }
}
