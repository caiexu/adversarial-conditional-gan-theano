"""Defines a model which will retrain a non-conditional GAN as a
cGAN."""

import numpy as np
from pylearn2.linear.matrixmul import MatrixMul
from pylearn2.models.mlp import MLP
from pylearn2.space import CompositeSpace
from pylearn2.utils import sharedX

from conditional import ConditionalAdversaryPair, ConditionalGenerator, ConditionalDiscriminator


class RetrainingConditionalAdversaryPair(ConditionalAdversaryPair):
    # TODO custom learning rates for parameters of pretrained model
    def __init__(self, pretrained_model, condition_space, condition_distribution,
                 discriminator_condition_mlp, discriminator_joint_mlp,
                 input_source, new_W_irange,
                 inferer=None,
                 inference_monitoring_batch_size=128,
                 monitor_generator=True,
                 monitor_discriminator=True,
                 monitor_inference=True,
                 shrink_d=0.):
        """Initialize a retraining conditional model from a
        non-conditional model.

        NB: This is heavily coupled with the `AdversaryPair`
        implementation; for example, it assumes that the first layer
        of the generator is a particular rectified linear formulation.
        """

        assert isinstance(pretrained_model, ConditionalAdversaryPair)

        noise_space = pretrained_model.generator.get_input_space()
        self.condition_space = condition_space
        data_space = pretrained_model.discriminator.get_input_space()

        self.input_source = input_source
        self.output_space = self.discriminator.get_output_space()

        generator = self._prepare_generator(pretrained_model.generator, noise_space,
                                            condition_distribution, input_source)

        discriminator = self._prepare_discriminator(pretrained_model.discriminator,
                                                    discriminator_condition_mlp,
                                                    discriminator_joint_mlp,
                                                    input_source)

        super(ConditionalAdversaryPair, self).__init__(generator, discriminator,
                                                       data_space, self.condition_space,
                                                       inferer=inferer,
                                                       inference_monitoring_batch_size=inference_monitoring_batch_size,
                                                       monitor_generator=monitor_generator,
                                                       monitor_discriminator=monitor_discriminator,
                                                       monitor_inference=monitor_inference,
                                                       shrink_d=shrink_d)

    def _prepare_generator(self, generator, noise_space, condition_distribution, input_source)
        noise_dim = noise_space.get_total_dim()
        condition_dim = self.condition_space.get_total_dim()

        first_layer = generator.mlp.layers[0]
        pretrain_W, _ = first_layer.get_param_values()

        rng = generator.mlp.rng
        new_W = np.vstack((pretrain_W, rng.uniform(-new_W_irange, new_W_irange,
                                                   (condition_dim, pretrain_W.shape[1])))
        new_W = sharedX(new_W)
        new_W.name = first_layer.name + '_retrain'

        first_layer.transformer = MatrixMul(new_W)
        first_layer.input_space = CompositeSpace(components=[noise_space, self.condition_space])
        generator.mlp.input_space = first_layer.input_space
        generator.mlp.input_source = input_source

        return ConditionalGenerator(generator.mlp, input_condition_space=self.condition_space,
                                    condition_distribution=condition_distribution, noise_dim=noise_dim)

    def _prepare_discriminator(self, discriminator, discriminator_condition_mlp,
                               discriminator_joint_mlp, input_source):
        # TODO makes a fixed modification to the existing discriminator:
        # just chop off the final layer. Now this becomes the "data MLP"
        # for the conditioned model.
        assert isinstance(discriminator, MLP)
        del discriminator.layers[-1]

        return ConditionalDiscriminator(discriminator, discriminator_condition_mlp,
                                        discriminator_joint_mlp, discriminator.input_space,
                                        self.condition_space)