package verification;

import org.junit.platform.launcher.LauncherSession;
import org.junit.platform.launcher.LauncherSessionListener;

/** Keep MavenPaths and the older MavenTestingUtils on the same per-suite fixture. */
public final class SuiteFixtureBase implements LauncherSessionListener
{
    private String previous;
    private boolean applied;

    @Override
    public void launcherSessionOpened(LauncherSession session)
    {
        String fixture = System.getProperty("jetty.test.fixture.base");
        if (fixture != null)
        {
            previous = System.setProperty("basedir", fixture);
            applied = true;
        }
    }

    @Override
    public void launcherSessionClosed(LauncherSession session)
    {
        if (applied)
        {
            if (previous == null)
                System.clearProperty("basedir");
            else
                System.setProperty("basedir", previous);
        }
    }
}
