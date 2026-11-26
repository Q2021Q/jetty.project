package verification;

import java.io.ByteArrayInputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyStore;
import java.time.Duration;
import java.util.List;
import java.util.ServiceLoader;
import java.util.zip.GZIPInputStream;
import javax.net.ssl.SSLContext;
import javax.net.ssl.TrustManagerFactory;

import org.eclipse.jetty.alpn.server.ALPNServerConnectionFactory;
import org.eclipse.jetty.compression.Compression;
import org.eclipse.jetty.compression.server.CompressionHandler;
import org.eclipse.jetty.http.HttpFieldPreEncoder;
import org.eclipse.jetty.http.HttpVersion;
import org.eclipse.jetty.http2.server.HTTP2ServerConnectionFactory;
import org.eclipse.jetty.io.ssl.ALPNProcessor;
import org.eclipse.jetty.server.Handler;
import org.eclipse.jetty.server.HttpConfiguration;
import org.eclipse.jetty.server.HttpConnectionFactory;
import org.eclipse.jetty.server.Request;
import org.eclipse.jetty.server.Response;
import org.eclipse.jetty.server.SecureRequestCustomizer;
import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.server.ServerConnector;
import org.eclipse.jetty.server.SslConnectionFactory;
import org.eclipse.jetty.util.Callback;
import org.eclipse.jetty.util.Jetty;
import org.eclipse.jetty.util.ssl.SslContextFactory;
import org.eclipse.jetty.io.Content;

public final class ConsumerSmoke
{
    private static final String BODY = "Jetty consolidate verification — UTF-8. ".repeat(150);
    private static final char[] FIXTURE_PASSWORD = "fixture-password".toCharArray();

    public static void main(String[] args) throws Exception
    {
        verifyOrigins();
        verifyServices();

        KeyStore keyStore = KeyStore.getInstance("PKCS12");
        try (var input = Files.newInputStream(Path.of(args[0])))
        {
            keyStore.load(input, FIXTURE_PASSWORD);
        }
        TrustManagerFactory trust = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
        trust.init(keyStore);
        SSLContext clientTls = SSLContext.getInstance("TLS");
        clientTls.init(null, trust.getTrustManagers(), null);

        Server server = new Server();
        ServerConnector plain = new ServerConnector(server);
        plain.setHost("127.0.0.1");
        server.addConnector(plain);

        HttpConfiguration secure = new HttpConfiguration();
        secure.addCustomizer(new SecureRequestCustomizer());
        HttpConnectionFactory http11 = new HttpConnectionFactory(secure);
        HTTP2ServerConnectionFactory http2 = new HTTP2ServerConnectionFactory(secure);
        ALPNServerConnectionFactory alpn = new ALPNServerConnectionFactory();
        alpn.setDefaultProtocol(http11.getProtocol());
        SslContextFactory.Server tls = new SslContextFactory.Server();
        tls.setKeyStore(keyStore);
        tls.setKeyStorePassword(String.valueOf(FIXTURE_PASSWORD));
        ServerConnector encrypted = new ServerConnector(server,
            new SslConnectionFactory(tls, alpn.getProtocol()), alpn, http2, http11);
        encrypted.setHost("127.0.0.1");
        server.addConnector(encrypted);

        CompressionHandler compression = new CompressionHandler(new Handler.Abstract()
        {
            @Override
            public boolean handle(Request request, Response response, Callback callback)
            {
                response.getHeaders().put("Content-Type", "text/plain; charset=UTF-8");
                Content.Sink.write(response, true, BODY, callback);
                return true;
            }
        });
        server.setHandler(compression);
        try
        {
            server.start();
            HttpClient client = HttpClient.newBuilder()
                .sslContext(clientTls).connectTimeout(Duration.ofSeconds(5)).build();
            check(client, "http://localhost:" + plain.getLocalPort(), HttpClient.Version.HTTP_1_1, false);
            check(client, "http://localhost:" + plain.getLocalPort(), HttpClient.Version.HTTP_1_1, true);
            check(client, "https://localhost:" + encrypted.getLocalPort(), HttpClient.Version.HTTP_2, true);
            check(client, "https://localhost:" + encrypted.getLocalPort(), HttpClient.Version.HTTP_1_1, false);
        }
        finally
        {
            server.stop();
        }
    }

    private static void verifyServices()
    {
        var preEncoders = ServiceLoader.load(HttpFieldPreEncoder.class).stream().map(ServiceLoader.Provider::get)
            .map(HttpFieldPreEncoder::getHttpVersion).toList();
        require(preEncoders.size() == 3 && preEncoders.containsAll(
            List.of(HttpVersion.HTTP_1_0, HttpVersion.HTTP_1_1, HttpVersion.HTTP_2)), "pre-encoders " + preEncoders);
        require(ServiceLoader.load(ALPNProcessor.Server.class).stream().anyMatch(provider ->
            provider.type().getName().endsWith(".JDK9ServerALPNProcessor")), "JSSE ALPN provider");
        require(ServiceLoader.load(Compression.class).stream().anyMatch(provider ->
            provider.type().getName().endsWith(".GzipCompression")), "gzip provider");
        require(Jetty.VERSION.equals("12.1.15"), "metadata Jetty.VERSION=" + Jetty.VERSION);
        System.out.println("PASS Jetty.VERSION, HTTP pre-encoders, ALPN and gzip via ServiceLoader");
    }

    private static void verifyOrigins() throws Exception
    {
        URI jar = Server.class.getProtectionDomain().getCodeSource().getLocation().toURI();
        require(jar.toString().endsWith("/jetty-core-consolidated-12.1.15.jar"), "consumer JAR " + jar);
        require(System.getProperty("java.class.path").contains("slf4j-api"), "SLF4J API present");
        for (String entry : System.getProperty("java.class.path").split(
            java.util.regex.Pattern.quote(java.io.File.pathSeparator)))
        {
            String file = Path.of(entry).getFileName().toString();
            require(!file.startsWith("jetty-") || file.equals("jetty-core-consolidated-12.1.15.jar"),
                "unexpected Jetty JAR " + file);
        }
        for (String symbol : List.of(
            "server.Server", "http.HttpParser", "io.EndPoint", "util.Jetty",
            "alpn.server.ALPNServerConnectionFactory", "alpn.java.server.JDK9ServerALPNProcessor",
            "http2.server.HTTP2ServerConnectionFactory", "http2.HTTP2Session", "http2.hpack.HpackDecoder",
            "security.SecurityHandler", "rewrite.handler.RewriteHandler",
            "compression.server.CompressionHandler", "compression.Compression", "compression.gzip.GzipCompression"))
        {
            String name = "org.eclipse.jetty." + symbol;
            Class<?> type = Class.forName(name, false, ConsumerSmoke.class.getClassLoader());
            require(type.getProtectionDomain().getCodeSource().getLocation().toURI().equals(jar), "origin for " + name);
            var resources = ConsumerSmoke.class.getClassLoader().getResources(name.replace('.', '/') + ".class");
            require(resources.hasMoreElements(), "missing class resource " + name);
            resources.nextElement();
            require(!resources.hasMoreElements(), "duplicate class resource " + name);
        }
        System.out.println("PASS all 14 representative classes from " + jar);
    }

    private static void check(HttpClient client, String address, HttpClient.Version version, boolean gzip) throws Exception
    {
        var builder = HttpRequest.newBuilder(URI.create(address + "/")).version(version).timeout(Duration.ofSeconds(10));
        if (gzip)
            builder.header("Accept-Encoding", "gzip");
        var response = client.send(builder.build(), HttpResponse.BodyHandlers.ofByteArray());
        require(response.statusCode() == 200, "status " + response.statusCode());
        require(response.version() == version, "protocol " + response.version());
        require(response.headers().firstValue("Content-Encoding").orElse("").equals(gzip ? "gzip" : ""), "encoding");
        byte[] bytes = response.body();
        if (gzip)
        {
            try (var input = new GZIPInputStream(new ByteArrayInputStream(bytes)))
            {
                bytes = input.readAllBytes();
            }
        }
        require(new String(bytes, StandardCharsets.UTF_8).equals(BODY), "exact payload");
        System.out.println("PASS " + address + " " + version + " gzip=" + gzip);
    }

    private static void require(boolean condition, String message)
    {
        if (!condition)
            throw new AssertionError(message);
    }
}
