package client;

import client.services.ControllerService;
import client.services.DefaultJamepadService;
import client.services.KeyboardService;
import client.services.bot.DiscordService;
import javafx.application.Application;
import javafx.fxml.FXMLLoader;
import javafx.geometry.Rectangle2D;
import javafx.scene.Scene;
import javafx.scene.image.Image;
import javafx.scene.layout.GridPane;
import javafx.stage.Screen;
import javafx.stage.Stage;
import org.jetbrains.annotations.Nullable;

import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Locale;
import java.util.Properties;
import java.util.ResourceBundle;

public final class Client extends Application {

    public static final ResourceBundle RESOURCE_BUNDLE =
            ResourceBundle.getBundle("client", Locale.getDefault());

    public static void main(final String[] args) {
        launch(args);
    }

    @Override
    public void start(final Stage primaryStage) throws Exception {
        final FXMLLoader loader = new FXMLLoader(
                Client.class.getResource("/view/client.fxml"), RESOURCE_BUNDLE);
        final GridPane page = loader.load();
        final Scene scene = new Scene(page);

        final ClientController clientController = loader.getController();

        final ArrayList<ControllerService> services = getAvailableServices();
        clientController.setControllerServices(services);

        primaryStage.setTitle(RESOURCE_BUNDLE.getString("client.title"));
        primaryStage.getIcons().add(new Image(getClass().getClassLoader().getResourceAsStream("icon.png")));
        primaryStage.setScene(scene);
        primaryStage.setResizable(false);
        primaryStage.show();

        final Rectangle2D bounds = Screen.getPrimary().getVisualBounds();
        primaryStage.setX(bounds.getWidth()/2 - primaryStage.getWidth());
        primaryStage.setY((bounds.getHeight() - primaryStage.getHeight()) / 2);
    }

    @Override
    public void stop() throws Exception {
        super.stop();
        System.exit(0);
    }

    private static ArrayList<ControllerService> getAvailableServices() {
        final ArrayList<DefaultJamepadService> jamepadServiceList = JamepadManager.getAvailableJamepadServices();
        final ArrayList<ControllerService> allServices = new ArrayList<>(2 + jamepadServiceList.size());
        allServices.add(new KeyboardService());
        final String token = getDiscordToken();
        if (token != null) {
            allServices.add(new DiscordService(token));
        }
        allServices.addAll(jamepadServiceList);

        return allServices;
    }

    @Nullable
    private static String getDiscordToken() {
        try (final InputStream input
                     = Client.class.getClassLoader().getResourceAsStream("discord.properties")) {

            final Properties prop = new Properties();
            if (input == null) {
                // Unable to find discord.properties
                return null;
            }

            // load a properties file from class path, inside static method
            prop.load(input);

            //get the property value and print it out
            return prop.getProperty("DiscordBotToken", null);
        } catch (final IOException ex) {
            return null;
        }
    }
}
