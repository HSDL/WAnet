from mpl_toolkits.mplot3d import Axes3D
import WAnet.application
import matplotlib.pyplot
import numpy
import pkg_resources


def _cuboid_data(pos, size=(1, 1, 1)):
    # code taken from
    # https://stackoverflow.com/a/35978146/4124317
    # suppose axis direction: x: to left; y: to inside; z: to upper
    # get the (left, outside, bottom) point
    o = [a - b / 2 for a, b in zip(pos, size)]
    l, w, h = size
    x = [[o[0], o[0] + l, o[0] + l, o[0], o[0]],
         [o[0], o[0] + l, o[0] + l, o[0], o[0]],
         [o[0], o[0] + l, o[0] + l, o[0], o[0]],
         [o[0], o[0] + l, o[0] + l, o[0], o[0]]]
    y = [[o[1], o[1], o[1] + w, o[1] + w, o[1]],
         [o[1], o[1], o[1] + w, o[1] + w, o[1]],
         [o[1], o[1], o[1], o[1], o[1]],
         [o[1] + w, o[1] + w, o[1] + w, o[1] + w, o[1] + w]]
    z = [[o[2], o[2], o[2], o[2], o[2]],
         [o[2] + h, o[2] + h, o[2] + h, o[2] + h, o[2] + h],
         [o[2], o[2], o[2] + h, o[2] + h, o[2]],
         [o[2], o[2], o[2] + h, o[2] + h, o[2]]]
    return x, y, z


def _plot_cube(position=(0, 0, 0), ax=None, color='b', size=1):
    x, y, z = _cuboid_data(position, size=(size, size, size))
    ax.plot_surface(x, y, z, color=color, rstride=1, cstride=1, alpha=size)


def _plot_dot(position=(0, 0, 0), ax=None, color='b', size=1):
    ax.scatter(position[0], position[1], position[2], color=color)


def plot_voxels(ax, matrix, color, quick):
    # plot a Matrix
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            for k in range(matrix.shape[2]):
                if matrix[i, j, k] > 0.51:
                    if quick:
                        _plot_dot(position=(i-0.5, j-0.5, k-0.5), ax=ax, color=color)
                    else:
                        _plot_cube(position=(i-0.5, j-0.5, k-0.5), ax=ax, color=color)

    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.set_zticklabels([])

    g = len(matrix[0, 0, :])
    ax.set_xlim((0, g-1))
    ax.set_ylim((0, g-1))
    ax.set_zlim((0, g-1))
    ax.set_aspect('equal')


def plot_curves(ax, true, line_style, topper):
    f = len(true[0, :])
    ax.plot(range(f), true[0, :], 'r'+line_style,
            range(f), true[1, :], 'b'+line_style,
            range(f), true[2, :], 'g'+line_style,
            )
    ax.set_xticklabels([])
    ax.set_yticklabels([])

    # Get and reset ylim
    y0, y1 = ax.get_ylim()
    ax.set_ylim([y0, topper])

    # Scale to square
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    ax.set_aspect((x1 - x0) / (y1 - y0))

def plot_examples(case, nx, ny, quick=True):
    # Load network
    structure = pkg_resources.resource_filename("WAnet", "trained_models/"+case+"_structure.yml")
    weights = pkg_resources.resource_filename("WAnet", "trained_models/"+case+"_weights.h5")
    nw = WAnet.application.Network(structure, weights)

    # Find out if its an autoencoder or a predictor
    if nw.network.layers[0].input_shape[1] == nw.network.layers[-1].output_shape[1]:
        mult = 2
    else:
        mult = 3

    for i in range(1, nx*ny*mult, mult):
        [_, ip, ot, op] = nw.prediction()
        idx = i

        y_top = 0
        if len(ip.shape) == 2:
            y_top = 1.1*numpy.max([y_top, numpy.max(ip.flatten())])
        if len(ot.shape) == 2:
            y_top = 1.1*numpy.max([y_top, numpy.max(ot.flatten())])
        if len(op.shape) == 2:
            y_top = 1.1*numpy.max([y_top, numpy.max(op.flatten())])

        print(y_top)

        # Plot input
        if len(ip.flatten()) == pow(nw.G, 3):
            ax = matplotlib.pyplot.subplot(ny, nx * mult, idx, projection='3d')
            plot_voxels(ax, ip, 'b', quick)
        else:
            ax = matplotlib.pyplot.subplot(ny, nx * mult, idx)
            plot_curves(ax, ip, '-', y_top)

        # Plot true output
        if mult == 3:
            idx = idx + 1
            if len(op.flatten()) == pow(nw.G, 3):
                ax = matplotlib.pyplot.subplot(ny, nx * mult, idx, projection='3d')
                plot_voxels(ax, ot, 'b', quick)
            else:
                ax = matplotlib.pyplot.subplot(ny, nx*mult, idx)
                plot_curves(ax, ot, '-', y_top)

        # Plot predicted output
        idx = idx + 1
        if len(op.flatten()) == pow(nw.G, 3):
            ax = matplotlib.pyplot.subplot(ny, nx * mult, idx, projection='3d')
            plot_voxels(ax, op, 'g', quick)
        else:
            ax = matplotlib.pyplot.subplot(ny, nx*mult, idx)
            plot_curves(ax, op, '--', y_top)

    matplotlib.pyplot.savefig(pkg_resources.resource_filename("WAnet", "figures/"+case+"_examples.png"), dpi=1000)

