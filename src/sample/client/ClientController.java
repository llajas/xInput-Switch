package client;

import client.services.ControllerService;
import javafx.beans.binding.Bindings;
import javafx.collections.FXCollections;
import javafx.collections.ObservableList;
import javafx.event.ActionEvent;
import javafx.fxml.FXML;
import javafx.scene.control.Button;
import javafx.scene.control.ChoiceBox;
import javafx.scene.control.TextField;
import javafx.util.StringConverter;

import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.regex.Pattern;

public class ClientController {

    private static final Pattern COMPILE = Pattern.compile("^[0-9A-F]+$");

    @FXML
    private TextField sessionIdField;
    @FXML
    private ChoiceBox<ControllerService> controllerInput;
    @FXML
    private Button startButton;

    @FXML
    private void initialize() {
        startButton.disableProperty().bind(Bindings.createBooleanBinding(
                () -> !sessionIdField.getText().matches("^[0-9A-F]+$")
                        || controllerInput.getValue() == null,
                sessionIdField.textProperty(), controllerInput.valueProperty()));

        // force the field to be hex only
        sessionIdField.textProperty().addListener((observable, oldValue, newValue) -> {
            if (!COMPILE.matcher(newValue.toUpperCase(Locale.ROOT)).matches() || newValue.length() > 4) {
                sessionIdField.setText(oldValue);
            }
        });
    }

    @FXML
    public void onEnter(final ActionEvent ae){
        if (!startButton.isDisabled()) {
            startButton.getOnAction().handle(ae);
        }
    }

    public void setControllerServices(final List<ControllerService> controllerServices) {
        final ObservableList<ControllerService> observableList = FXCollections.observableList(controllerServices);
        FXCollections.sort(observableList, Comparator.comparing(ControllerService::toString));
        controllerInput.setItems(observableList);
        controllerInput.getSelectionModel().selectFirst();
    }

    public void setButtonAction(final Runnable runnable) {
        startButton.setOnAction(event -> runnable.run());
    }

    public ControllerService getSelectedControllerService() {
        return controllerInput.getValue();
    }
}
