import keras
import sklearn.model_selection
import numpy
import pkg_resources
import os


def load_data():
    curves = numpy.load(pkg_resources.resource_filename('WAnet', 'data/compiled_data/data_curves.npz'))['curves']
    geometry = numpy.load(pkg_resources.resource_filename('WAnet', 'data/compiled_data/data_geometry.npz'))['geometry']
    constants = numpy.load(pkg_resources.resource_filename('WAnet', 'data/compiled_data/constants.npz'))
    S = constants['S']
    N = constants['N']
    D = constants['D']
    F = constants['F']
    G = constants['G']

    new_curves = numpy.zeros((S*N, D * F))
    for i, curveset in enumerate(curves):
        new_curves[i, :] = curveset.T.flatten() / 1000000

    new_geometry = numpy.zeros((S*N, G * G * G))
    for i, geometryset in enumerate(geometry):
        new_geometry[i, :] = geometryset.T.flatten()

    return curves, geometry, S, N, D, F, G, new_curves, new_geometry


def train_geometry_autoencoder(epochs, latent_dim, save_results, print_network):
    curves, geometry, S, N, D, F, G, new_curves, new_geometry = load_data()

    batch_size = 100
    original_dim = G*G*G
    intermediate_dim = 256
    epsilon_std = 1.0

    x = keras.layers.Input(shape=(original_dim,))
    h = keras.layers.Dense(intermediate_dim, activation='relu')(x)
    z_mean = keras.layers.Dense(latent_dim)(h)
    z_log_var = keras.layers.Dense(latent_dim)(h)

    def sampling(args):
        z_mean, z_log_var = args
        epsilon = keras.backend.random_normal(shape=(keras.backend.shape(z_mean)[0], latent_dim), mean=0.,
                                  stddev=epsilon_std)
        return z_mean + keras.backend.exp(z_log_var / 2) * epsilon

    # note that "output_shape" isn't necessary with the TensorFlow backend
    z = keras.layers.Lambda(sampling, output_shape=(latent_dim,))([z_mean, z_log_var])

    # we instantiate these layers separately so as to reuse them later
    decoder_h = keras.layers.Dense(intermediate_dim, activation='relu')
    decoder_mean = keras.layers.Dense(original_dim, activation='sigmoid')
    h_decoded = decoder_h(z)
    x_decoded_mean = decoder_mean(h_decoded)

    # Custom loss layer
    class CustomVariationalLayer(keras.layers.Layer):
        def __init__(self, **kwargs):
            self.is_placeholder = True
            super(CustomVariationalLayer, self).__init__(**kwargs)

        def vae_loss(self, x, x_decoded_mean):
            xent_loss = original_dim * keras.metrics.binary_crossentropy(x, x_decoded_mean)
            kl_loss = - 0.5 * keras.backend.sum(1 + z_log_var - keras.backend.square(z_mean)
                                                - keras.backend.exp(z_log_var), axis=-1)
            return keras.backend.mean(xent_loss + kl_loss)

        def call(self, inputs, **kwargs):
            x = inputs[0]
            x_decoded_mean = inputs[1]
            loss = self.vae_loss(x, x_decoded_mean)
            self.add_loss(loss, inputs=inputs)
            # We won't actually use the output.
            return x

    y = CustomVariationalLayer()([x, x_decoded_mean])
    vae = keras.models.Model(x, y)
    vae.compile(optimizer='rmsprop', loss=None)

    x_train, x_test = sklearn.model_selection.train_test_split(new_geometry)

    weights = pkg_resources.resource_filename('WAnet', 'trained_models/temp_vae_weights.h5')
    vae.fit(x_train,
            shuffle=True,
            epochs=epochs,
            batch_size=batch_size,
            validation_data=(x_test, None),
            verbose=1,
            callbacks=[keras.callbacks.ModelCheckpoint(filepath=weights, verbose=1, save_best_only=True)])

    vae.load_weights(weights)
    os.remove(weights)

    # build a model to project inputs on the latent space
    encoder = keras.models.Model(x, z_mean)

    # build a digit generator that can sample from the learned distribution
    decoder_input = keras.layers.Input(shape=(latent_dim,))
    _h_decoded = decoder_h(decoder_input)
    _x_decoded_mean = decoder_mean(_h_decoded)
    generator = keras.models.Model(decoder_input, _x_decoded_mean)

    # Build and save the autoencoder
    _h_decoded2 = decoder_h(z_mean)
    _x_decoded_mean2 = decoder_mean(_h_decoded2)
    autoencoder = keras.models.Model(x, _x_decoded_mean2)

    structure = []
    weights = []
    if save_results:
        # Save encoder structure and weights
        temp = open(pkg_resources.resource_filename('WAnet', 'trained_models/geometry_encoder_structure.yml'), 'w')
        temp.write(encoder.to_yaml())
        temp.close()
        encoder.save_weights(pkg_resources.resource_filename('WAnet', 'trained_models/geometry_encoder_weights.h5'))

        # Save decoder structure and weights
        temp = open(pkg_resources.resource_filename('WAnet', 'trained_models/geometry_decoder_structure.yml'), 'w')
        temp.write(generator.to_yaml())
        temp.close()
        generator.save_weights(pkg_resources.resource_filename('WAnet', 'trained_models/geometry_decoder_weights.h5'))

        # Save full autoencoder structure and weights
        structure = pkg_resources.resource_filename('WAnet', 'trained_models/geometry_autoencoder_structure.yml')
        weights = pkg_resources.resource_filename('WAnet', 'trained_models/geometry_autoencoder_weights.h5')
        temp = open(structure, 'w')
        temp.write(autoencoder.to_yaml())
        temp.close()
        autoencoder.save_weights(weights)

    if print_network:
        keras.utils.plot_model(generator, to_file=pkg_resources.resource_filename('WAnet', 'figures/geometry_decoder.eps'), show_shapes=True)
        keras.utils.plot_model(encoder, to_file=pkg_resources.resource_filename('WAnet', 'figures/geometry_encoder.eps'), show_shapes=True)
        keras.utils.plot_model(autoencoder, to_file=pkg_resources.resource_filename('WAnet', 'figures/geometry_autoencoder.eps'), show_shapes=True)

    return True


def train_response_autoencoder(epochs, latent_dim, save_results, print_network):
    curves, geometry, S, N, D, F, G, new_curves, new_geometry = load_data()

    batch_size = 10
    original_dim = D*F
    intermediate_dim = 64
    epsilon_std = 1.0

    x = keras.layers.Input(shape=(original_dim,))
    h = keras.layers.Dense(intermediate_dim, activation='relu')(x)
    z_mean = keras.layers.Dense(latent_dim)(h)
    z_log_var = keras.layers.Dense(latent_dim)(h)

    def sampling(args):
        z_mean, z_log_var = args
        epsilon = keras.backend.random_normal(shape=(keras.backend.shape(z_mean)[0], latent_dim), mean=0.,
                                  stddev=epsilon_std)
        return z_mean + keras.backend.exp(z_log_var / 2) * epsilon

    # note that "output_shape" isn't necessary with the TensorFlow backend
    z = keras.layers.Lambda(sampling, output_shape=(latent_dim,))([z_mean, z_log_var])

    # we instantiate these layers separately so as to reuse them later
    decoder_h = keras.layers.Dense(intermediate_dim, activation='relu')
    decoder_mean = keras.layers.Dense(original_dim, activation='sigmoid')
    h_decoded = decoder_h(z)
    x_decoded_mean = decoder_mean(h_decoded)

    # Custom loss layer
    class CustomVariationalLayer(keras.layers.Layer):
        def __init__(self, **kwargs):
            self.is_placeholder = True
            super(CustomVariationalLayer, self).__init__(**kwargs)

        def vae_loss(self, x, x_decoded_mean):
            xent_loss = original_dim * keras.metrics.mean_squared_error(x, x_decoded_mean)
            kl_loss = - 0.5 * keras.backend.sum(1 + z_log_var - keras.backend.square(z_mean) - keras.backend.exp(z_log_var), axis=-1)
            return keras.backend.mean(xent_loss + kl_loss)

        def call(self, inputs):
            x = inputs[0]
            x_decoded_mean = inputs[1]
            loss = self.vae_loss(x, x_decoded_mean)
            self.add_loss(loss, inputs=inputs)
            # We won't actually use the output.
            return x

    y = CustomVariationalLayer()([x, x_decoded_mean])
    vae = keras.models.Model(x, y)
    vae.compile(optimizer='rmsprop', loss=None)

    # train the VAE on MNIST digits
    x_train, x_test = sklearn.model_selection.train_test_split(new_curves)
    weights = pkg_resources.resource_filename('WAnet', 'trained_models/temp_vae_weights.h5')

    vae.fit(x_train,
            shuffle=True,
            epochs=epochs,
            batch_size=batch_size,
            validation_data=(x_test, None),
            verbose=1,
            callbacks=[keras.callbacks.ModelCheckpoint(filepath=weights, verbose=1, save_best_only=True)])

    vae.load_weights(weights)
    os.remove(weights)

    # build a model to project inputs on the latent space
    encoder = keras.models.Model(x, z_mean)

    # build a digit generator that can sample from the learned distribution
    decoder_input = keras.layers.Input(shape=(latent_dim,))
    _h_decoded = decoder_h(decoder_input)
    _x_decoded_mean = decoder_mean(_h_decoded)
    generator = keras.models.Model(decoder_input, _x_decoded_mean)

    # Build and save the autoencoder
    _h_decoded2 = decoder_h(z_mean)
    _x_decoded_mean2 = decoder_mean(_h_decoded2)
    autoencoder = keras.models.Model(x, _x_decoded_mean2)

    if save_results:
        # Save encoder structure and weights
        temp = open(pkg_resources.resource_filename('WAnet', 'trained_models/curve_encoder_structure.yml'), 'w')
        temp.write(encoder.to_yaml())
        temp.close()
        encoder.save_weights(pkg_resources.resource_filename('WAnet', 'trained_models/curve_encoder_weights.h5'))

        # Save decoder structure and weights
        temp = open(pkg_resources.resource_filename('WAnet', 'trained_models/curve_decoder_structure.yml'), 'w')
        temp.write(generator.to_yaml())
        temp.close()
        generator.save_weights(pkg_resources.resource_filename('WAnet', 'trained_models/curve_decoder_weights.h5'))

        # Save full autoencoder structure and weights
        structure = pkg_resources.resource_filename('WAnet', 'trained_models/curve_autoencoder_structure.yml')
        weights = pkg_resources.resource_filename('WAnet', 'trained_models/curve_autoencoder_weights.h5')
        temp = open(structure, 'w')
        temp.write(autoencoder.to_yaml())
        temp.close()
        autoencoder.save_weights(weights)

    if print_network:
        keras.utils.plot_model(generator, to_file=pkg_resources.resource_filename('WAnet', 'figures/curve_decoder.eps'), show_shapes=True)
        keras.utils.plot_model(encoder, to_file=pkg_resources.resource_filename('WAnet', 'figures/curve_encoder.eps'), show_shapes=True)
        keras.utils.plot_model(autoencoder, to_file=pkg_resources.resource_filename('WAnet', 'figures/curve_autoencoder.eps'), show_shapes=True)

    return True


def train_forward_network(epochs, latent_dim, save_results, print_network):
    curves, geometry, S, N, D, F, G, new_curves, new_geometry = load_data()

    # Define model
    x   = keras.layers.Input(shape=(32768,))
    de1 = keras.layers.Dense(256, activation='relu')(x)
    de2 = keras.layers.Dense(latent_dim, activation='relu')(de1)
    con = keras.layers.Dense(latent_dim, activation='relu')(de2)
    dd2 = keras.layers.Dense(64, activation='relu')(con)
    y   = keras.layers.Dense(192, activation='sigmoid')(dd2)

    # Build and compile ,model
    mdl = keras.models.Model(x, y)
    mdl.compile(optimizer='rmsprop', loss='mse')

    # # Instantiate and freeze layers if possible
    temp = open(pkg_resources.resource_filename('WAnet', 'trained_models/geometry_encoder_structure.yml'), 'r')
    geo = keras.models.model_from_yaml(temp.read())
    geo.load_weights(pkg_resources.resource_filename('WAnet', 'trained_models/geometry_encoder_weights.h5'))

    # Load curve autoencoder
    temp = open(pkg_resources.resource_filename('WAnet', 'trained_models/curve_decoder_structure.yml'), 'r')
    curve = keras.models.model_from_yaml(temp.read())
    curve.load_weights(pkg_resources.resource_filename('WAnet', 'trained_models/curve_decoder_weights.h5'))

    mdl.layers[1].set_weights(geo.layers[1].get_weights())
    mdl.layers[1].trainable = False
    mdl.layers[2].set_weights(geo.layers[2].get_weights())
    mdl.layers[2].trainable = False

    mdl.layers[4].set_weights(curve.layers[1].get_weights())
    mdl.layers[4].trainable = False
    mdl.layers[5].set_weights(curve.layers[2].get_weights())
    mdl.layers[5].trainable = False

    # Make file names
    weights = pkg_resources.resource_filename('WAnet', 'trained_models/forward_weights.h5')
    structure = pkg_resources.resource_filename('WAnet', 'trained_models/forward_structure.yml')
    plot = pkg_resources.resource_filename('WAnet', 'figures/forward.eps')

    # COmpute comparison
    m = numpy.mean(new_curves)
    mse = numpy.mean([(x-m)*(x-m) for x in new_curves])
    print(mse)

    # Save model structure and start training
    if save_results:
        mdl.fit(new_geometry, new_curves, verbose=1, epochs=epochs, shuffle=True, validation_split=0.2,
                callbacks=[keras.callbacks.ModelCheckpoint(filepath=weights, verbose=1, save_best_only=True)])

        # Save decoder structure and weights
        temp = open(structure, 'w')
        temp.write(mdl.to_yaml())
        temp.close()
    else:
        mdl.fit(new_geometry, new_curves, verbose=1, epochs=epochs, shuffle=True, validation_split=0.2)

    if print_network:
        keras.utils.plot_model(mdl, to_file=plot, show_shapes=True)

    return True


def train_inverse_network(epochs, latent_dim, save_results, print_network):
    curves, geometry, S, N, D, F, G, new_curves, new_geometry = load_data()

    # Define model
    x   = keras.layers.Input(shape=(192,))
    de1 = keras.layers.Dense(64, activation='relu')(x)
    de2 = keras.layers.Dense(latent_dim, activation='relu')(de1)
    con = keras.layers.Dense(latent_dim, activation='relu')(de2)
    dd2 = keras.layers.Dense(256, activation='relu')(con)
    y   = keras.layers.Dense(32768, activation='sigmoid')(dd2)

    # Build and compile ,model
    mdl = keras.models.Model(x, y)
    mdl.compile(optimizer='rmsprop', loss='binary_crossentropy')

    # # Instantiate and freeze layers if possible
    temp = open(pkg_resources.resource_filename('WAnet', 'trained_models/geometry_decoder_structure.yml'), 'r')
    geo = keras.models.model_from_yaml(temp.read())
    geo.load_weights(pkg_resources.resource_filename('WAnet', 'trained_models/geometry_decoder_weights.h5'))

    # Load curve autoencoder
    temp = open(pkg_resources.resource_filename('WAnet', 'trained_models/curve_encoder_structure.yml'), 'r')
    curve = keras.models.model_from_yaml(temp.read())
    curve.load_weights(pkg_resources.resource_filename('WAnet', 'trained_models/curve_encoder_weights.h5'))

    mdl.layers[1].set_weights(curve.layers[1].get_weights())
    mdl.layers[1].trainable = False
    mdl.layers[2].set_weights(curve.layers[2].get_weights())
    mdl.layers[2].trainable = False

    mdl.layers[4].set_weights(geo.layers[1].get_weights())
    mdl.layers[4].trainable = False
    mdl.layers[5].set_weights(geo.layers[2].get_weights())
    mdl.layers[5].trainable = False

    # Make file names
    weights = pkg_resources.resource_filename('WAnet', 'trained_models/inverse_weights.h5')
    structure = pkg_resources.resource_filename('WAnet', 'trained_models/inverse_structure.yml')
    plot = pkg_resources.resource_filename('WAnet', 'figures/inverse.eps')

    # Save model structure and start training
    if save_results:
        mdl.fit(new_curves, new_geometry, verbose=1, epochs=epochs, shuffle=True, validation_split=0.2,
                callbacks=[keras.callbacks.ModelCheckpoint(filepath=weights, verbose=1, save_best_only=True)])
        # Save decoder structure and weights
        temp = open(structure, 'w')
        temp.write(mdl.to_yaml())
        temp.close()
    else:
        mdl.fit(new_curves, new_geometry, verbose=1, epochs=epochs, shuffle=True, validation_split=0.2)

    if print_network:
        keras.utils.plot_model(mdl, to_file=plot, show_shapes=True)

    return True