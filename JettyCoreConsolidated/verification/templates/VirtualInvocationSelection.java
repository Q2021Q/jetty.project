
package jcv;
import org.junit.jupiter.api.extension.ConditionEvaluationResult;
import org.junit.jupiter.api.extension.ExecutionCondition;
import org.junit.jupiter.api.extension.ExtensionContext;
import java.util.regex.Pattern;

public final class VirtualInvocationSelection implements ExecutionCondition {
    private static final Pattern INVOCATION = Pattern.compile("\\[test-template-invocation:#([0-9]+)]$");
    @Override
    public ConditionEvaluationResult evaluateExecutionCondition(ExtensionContext context) {
        if (context.getTestClass().filter(c ->
                c.getName().equals("org.eclipse.jetty.util.thread.strategy.ExecutionStrategyTest")).isPresent()) {
            var match = INVOCATION.matcher(context.getUniqueId());
            if (match.find() && Integer.parseInt(match.group(1)) <= 6)
                return ConditionEvaluationResult.disabled(
                    "vt21-selection: platform invocation covered in the JDK 17 reactor");
        }
        return ConditionEvaluationResult.enabled("selected original invocation");
    }
}
